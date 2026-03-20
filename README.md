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
Built with a business partner (accountant & Allegro seller) to track real per-order profit margins - including hidden operational costs(shipping returns, Allegro commissions, VAT adjustments) that Allegro's dashboard doesn't show.

Integrates with Allegro API via OAuth2+PKCE, ingests order data asynchronously using Celery polling (webhook emulation), and calculates per-order profit after seller costs. Allegro API does not provide webhooks, so polling was implemented to emulate real-time order ingestion.

---

## Live / Demo
* **90s: [▶link]** - Architecture summary, UI, CI/CD pipeline with cache invalidation
* **5-min deep-dive: [▶link]** - Architecture walkthrough, terraform apply, OAuth2 PKCE 
  flow, UI, polling, CI/CD pipeline with cache invalidation

**Recommended:** Start with the 90s video, 
then check Code Highlights below.

---

## Tech Stack
* **Cloud (AWS):** VPC, ECS Fargate, ECR, ALB, CloudFront (with VPC Origin), RDS (PostgreSQL), Secrets Manager, IAM, CloudWatch, NAT Gateway, VPC Endpoints, ElastiCache
* **DevOps:** Terraform, Docker, GitHub Actions, Git
* **Backend:** Python (Django DRF), Celery, Redis, OAuth2 (PKCE)
* **Frontend:** React, Nginx, JavaScript

---

## Architecture & UI
![Architecture](./images/AWS_DIAGRAM2.png)

![UI](./images/ss-app.png)

---

## Code Highlights
- [entrypoint.sh](./Backend/entrypoint.sh) - Ensures DB is ready, and then runs migrations
````bash
while ! python -c "socket check..."; do
    echo "Database is not ready..."; sleep 4
done
````

- [setup_allegro_cred.py](./Backend/allegro_app/management/commands/setup_allegro_cred.py) - Idempotent credential seeding from Secrets Manager
``````python
        if not client_id or not client_secret:
            logger.error('No creds in json!')
            return

        obj, created = AllegroCredentials.objects.get_or_create(id=1)

        obj.client_id = client_id
        obj.set_client_secret(client_secret)
        obj.redirect_uri = redirect_uri
        obj.is_sandbox = is_sandbox_env
        obj.save()
``````

- [Secrets_Manager.tf](./Terraform/Secrets_Manager.tf) - No hardcoded secrets; everything is generated dynamically
`````terraform
resource "aws_secretsmanager_secret_version" "terraform_generated" {
  secret_id     = aws_secretsmanager_secret.terraform_generated.id
  secret_string = jsonencode(merge(
    jsondecode(data.aws_secretsmanager_secret_version.manual.secret_string),
    {
      # RDS credentials
      db_username = var.db_username
      db_password = random_password.db_password.result
`````

- [OAuth2/models.py](./Backend/allegro_app/OAuth2/models.py) - Fernet encryption at the model level, not the application level
``````python
class AllegroCredentials(models.Model):
     encrypted_client_secret = models.CharField(max_length=512)

    def set_client_secret(self, secret: str) -> None:
        """Encrypt and store the client secret."""
        self.encrypted_client_secret = settings.PRIMARY_FERNET.encrypt(secret.encode()).decode()

    def get_client_secret(self) -> str:
        """Decrypt and return the client secret."""
        return settings.FERNET.decrypt(self.encrypted_client_secret.encode()).decode()
``````

- [OAuth2/services.py](./Backend/allegro_app/OAuth2/services.py) - Validation before use - fail fast instead of a silent error
``````python
    @staticmethod
    def require_client_secret(creds: AllegroCredentials) -> str:
        secret = creds.get_client_secret().strip()
        if not secret:
            raise ValueError("Allegro client_secret is missing")
        return secret
``````

---

## Key Features
- Infrastructure as Code using Terraform (~68 resources) divided into modules: Networking, Compute, Scaling, Security, and Observability
- OAuth2 + PKCE login flow with Allegro
- Idempotent data ingestion via polling
- Per-order margin calculation with cost breakdown
- Asynchronous processing with Celery workers
- Fernet-encrypted credential storage

---

## CI/CD
**CI/CD Flow:**

**Frontend:** `GitHub Actions` ➔ `Docker Build` ➔ `Amazon ECR` ➔ `ECS (versioned)` ➔ `CloudFront Invalidation`

**Backend:** `GitHub Actions` ➔ `Docker Build` ➔ `Amazon ECR` ➔ `ECS (versioned)`

**Container Entrypoint:**
`Wait for DB` ➔ `Migrations` ➔ `Seeds` ➔ `App Ready`

---

## Scaling Strategy
* ECS Service Auto Scaling (CPU / Memory based)
* ALB distributes traffic across tasks
* CloudFront reduces origin load
* ElastiCache reduces database pressure

---

## Security
* No public access to ECS or ALB - traffic enters only via CloudFront
* Secrets stored in AWS Secrets Manager - no hardcoded credentials, 
  dynamically generated by Terraform
* Private subnets for compute
* VPC Endpoints for ECR, CW and Secrets Manager - no internet traversal 
  for sensitive operations
* Fernet encryption for third-party API credentials at the model level

---

## Design Evolution
The project was developed iteratively. Evolved from local Docker-Compose to **Render**, eventually migrating to **AWS**. 
Initial EC2 deployments were refactored into a high-availability Fargate Multi-AZ architecture. 
This transition addressed real-world trade-offs between management overhead, cost optimization, and infrastructure resilience using Terraform.

---

## Possible Improvements
* Add SQS for async processing
* Add unit tests
* Add Run Migrations Task in CI/CD to avoid a potential race condition
* Add WAF for edge protection
* Add distributed tracing (X-Ray)
* Implement blue/green deployments

---

## Author
Łukasz Sanecki