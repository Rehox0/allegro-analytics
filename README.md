# Allegro Profit & Margin Analytics
**Portfolio project demonstrating cloud-native development on AWS.**


![AWS](https://img.shields.io/badge/AWS-FF9900?logo=amazonaws)
![Terraform Version](https://img.shields.io/badge/Terraform-v1.14.7-7B42BC?logo=terraform)
![Docker Version](https://img.shields.io/badge/Docker-28.2.2-2496ED?logo=docker)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?logo=github-actions&logoColor=white)
![Python Version](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)
![Django Version](https://img.shields.io/badge/Django-5.2.8-092E20?logo=django)
![React Version](https://img.shields.io/badge/React-19.2.0-61DAFB?logo=react)
![Celery Version](https://img.shields.io/badge/Celery-5.5.3-37814A?logo=celery)
![Valkey](https://img.shields.io/badge/Valkey-5FBB97?logo=valkey&logoColor=white)

## Overview
Built with a business partner (accountant & Allegro seller) to track real per-order profit margins - including hidden operational costs (shipping returns, Allegro commissions, VAT adjustments) that Allegro's dashboard doesn't show.

Integrates with Allegro API via OAuth2+PKCE, ingests data asynchronously using Celery polling (webhook emulation), and calculates per-order profit after seller costs. Allegro API does not provide webhooks, so polling was implemented to emulate real-time order ingestion.

---

## Live / Demo
* **[▶100s](https://youtu.be/V-9K6OLjeVw)**: Architecture summary ➔ UI ➔ CI/CD pipeline with cache invalidation
* **[▶5-min deep-dive](https://youtu.be/W43Mq82sgeU)**:  
  [Architecture walkthrough](https://youtu.be/W43Mq82sgeU?t=12) ➔ [terraform apply](https://youtu.be/W43Mq82sgeU?t=40) ➔ [OAuth2 PKCE flow](https://youtu.be/W43Mq82sgeU?t=101) ➔ [UI+features](https://youtu.be/W43Mq82sgeU?t=157) ➔ [polling+logs](https://youtu.be/W43Mq82sgeU?t=198) ➔ [CI/CD with cache invalidation](https://youtu.be/W43Mq82sgeU?t=243)


**Recommended:** Start with the **[▶5-min deep-dive](https://youtu.be/W43Mq82sgeU)** video, or jump to a specific section above.

---

## Tech Stack
* **Cloud (AWS):** VPC, ECS Fargate, ECR, ALB, CloudFront (with VPC Origin), RDS (PostgreSQL), Secrets Manager, IAM, CloudWatch, NAT Gateway, VPC Endpoints, ElastiCache
* **DevOps:** Terraform, Docker, GitHub Actions, Git
* **Backend:** Python (Django DRF), Celery, Redis/Valkey, OAuth2 (PKCE)
* **Frontend:** React, Nginx, JavaScript

---

## Architecture
![Architecture](./images/AWS_DIAGRAM.png)
<image-card alt="Architecture" src="images/AWS_DIAGRAM.png" ></image-card>

- **Infrastructure as Code using Terraform (~68 resources)** - networking, compute, database, security, scaling, and observability.
- **Remote state** stored in S3 with AES-256 encryption; single `terraform.tfstate` scoped to `eu-north-1`.
- **Target Tracking Scaling** for Frontend, Backend, and workers; poller runs as a single instance to avoid concurrent cursor reads on the same stream.
- **Security Groups** enforce strict inbound/outbound rules between layers (`CloudFront` via `VPC Origin` → `ALB` → `ECS` → `RDS/ElastiCache`).
- **CloudFront** is the sole entry point - ALB and ECS tasks have no public access; outbound internet access for ECS routed via **NAT Gateway**
- **ElastiCache** (Valkey) for caching layer, Redis for Celery broker

---

## Local Development
> Repository is private. Full setup documentation exists in private repository.
  Demo available in the video above.

---

## CI/CD

**Frontend:** `GitHub Actions` ➔ `Docker Build` ➔ `Amazon ECR` ➔ `ECS (versioned)` ➔ `CloudFront Invalidation`

**Backend:** `GitHub Actions` ➔ `Docker Build` ➔ `Amazon ECR` ➔ `ECS (versioned)`

**Container Entrypoint:**
`Wait for DB` ➔ `Migrations` ➔ `Seeding data` ➔ `App Ready`

---

## Code Highlights
- [Secrets_Manager.tf](./Terraform/Secrets_Manager.tf) - All secrets are generated dynamically by Terraform; nothing is hardcoded or committed.
```terraform
resource "aws_secretsmanager_secret_version" "terraform_generated" {
  secret_id     = aws_secretsmanager_secret.terraform_generated.id
  secret_string = jsonencode(merge(
    jsondecode(data.aws_secretsmanager_secret_version.manual.secret_string),
    {
      # RDS credentials
      db_username = var.db_username
      db_password = random_password.db_password.result
```

- [entrypoint.sh](./Backend/entrypoint.sh) - DB readiness check using only Python's stdlib; no netcat or postgresql-client needed in the container image.
```bash
# Simplified
while ! python -c "
    aws_secrets = json.loads(os.environ.get('secrets_json', '{}'))
    s.connect((aws_secrets.get('db_host'), aws_secrets.get('db_port', 5432)))
" > /dev/null 2>&1; do
    sleep 4
done
```

- [setup_allegro_cred.py](./Backend/allegro_app/management/commands/setup_allegro_cred.py) - Idempotent credential seeding; safe to run on every container startup without duplicating records.
```python
# Simplified
@transaction.atomic
def handle(self, *args, **options):
  obj, created = AllegroCredentials.objects.get_or_create(id=1)
  obj.client_id = client_id
  obj.set_client_secret(client_secret) # Fernet-encrypted at model level
  obj.save()
```



- **OAuth2/models.py** - Fernet encryption lives at the model level; the plaintext secret never reaches the application layer or logs.
```python
class AllegroCredentials(models.Model):
     encrypted_client_secret = models.CharField(max_length=512)

    def set_client_secret(self, secret: str) -> None:
        """Encrypt and store the client secret."""
        self.encrypted_client_secret = settings.PRIMARY_FERNET.encrypt(secret.encode()).decode()

    def get_client_secret(self) -> str:
        """Decrypt and return the client secret."""
        return settings.FERNET.decrypt(self.encrypted_client_secret.encode()).decode()
```

- **OAuth2/services.py** - Fail fast before any API call; misconfigured credentials surface immediately instead of causing silent failures downstream.
```python
    @staticmethod
    def require_client_secret(creds: AllegroCredentials) -> str:
        secret = creds.get_client_secret().strip()
        if not secret:
            raise ValueError("Allegro client_secret is missing. Update Allegro credentials in Django Admin.")
        return secret
```

---

## Scaling Strategy
* ECS Service Auto Scaling (CPU / Memory based)
* ALB distributes traffic across tasks
* CloudFront reduces origin load
* ElastiCache reduces database pressure

---

## Security
* Secrets stored in AWS Secrets Manager - no hardcoded credentials, dynamically generated by Terraform
* Private subnets for compute and RDS/ElastiCache
* VPC Endpoints for ECR, CW and Secrets Manager - no internet exposure for sensitive operations
* Fernet encryption for third-party API credentials at the model level

---

## Design Evolution
Started as a learning project built for a business partner. Developed and iterated on **Render** for 4-5 months, then migrated to **AWS** after completing AWS certifications (CCP, DVA).

Initial infrastructure was provisioned manually via AWS Console - after ~20 hours, complexity and configuration drift made it unmanageable. Rebuilt from scratch; the second iteration worked but remained hard to reproduce. This drove the migration to **Terraform**, which resolved reproducibility and became the foundation for the final Multi-AZ Fargate architecture.

---

## Possible Improvements
* Add SQS for async processing - currently using a custom database-backed queue (PostgreSQL) with idempotent enqueue, worker locking, retry backoff, and dead-letter semantics. SQS would offload queue pressure from the database and provide managed delivery guarantees at scale.
* Add WAF for edge protection
* Add Run Migrations Task in CI/CD - current setup has a potential race condition when multiple tasks start simultaneously before migrations complete
* Add distributed tracing (X-Ray)
* Add unit tests - priority: margin calculation logic and Fernet encryption paths
* Implement blue/green deployments
* Add DynamoDB state locking - currently no concurrent write protection on the S3 backend.

---

## Author
Łukasz Sanecki