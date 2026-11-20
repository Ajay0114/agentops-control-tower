# AgentOps Control Tower

AgentOps Control Tower is a centralized application for managing and
monitoring AI agents and their operational activity.

## Overview

The application brings key agent operations into one place, including: -
Organizations and projects - AI agents and agent versions - Environments
and integrations - Agent executions and sessions - Telemetry events and
operational activity - API keys and user sessions

## Architecture

The application runs as three Docker Compose services:

  Service      Purpose                       Container port
  ------------ --------------------------- ----------------
  `frontend`   Web application (Next.js)             `3000`
  `api`        Backend API                           `8010`
  `postgres`   PostgreSQL database                   `5432`

The frontend communicates with the API, and the API connects to
PostgreSQL through the Docker Compose network. PostgreSQL data is stored
in the persistent Docker volume `agentops_postgres_data`.

## Technology

-   Frontend: Next.js
-   Backend: Python API
-   Database: PostgreSQL 16
-   Containers and deployment: Docker Compose and Coolify
-   Hosting: AWS EC2 (Ubuntu)

## Repository Structure

``` text
agentops-control-tower/
├── apps/
│   ├── frontend/       # Next.js web application
│   └── api/            # Backend API
├── docker-compose.yml  # Application services
└── README.md
```

## Run the Application

Run these commands from the repository root on a machine with Docker and
Docker Compose installed:

``` bash
docker compose up -d --build
docker compose ps
```

To run the backend API directly in development mode, execute this from
the repository root:

``` bash
uvicorn agentops_api.main:app --app-dir apps/api/src --reload --host 0.0.0.0 --port 8010
```

To follow service logs:

``` bash
docker compose logs -f
```

To stop the application:

``` bash
docker compose down
```

**Database note:** `docker compose down` preserves the named PostgreSQL
volume. Do not use `docker compose down -v` unless you intentionally
want to delete the database volume.

## Deployment -- AWS EC2 & Coolify

### Start the EC2 instance and connect

1.  Open AWS EC2: https://console.aws.amazon.com/ec2/

2.  Select region `us-east-1` and instance `agentops-coolify`.

3.  Select **Instance state → Start instance** and wait for `2/2` status
    checks.

4.  Copy the instance's current **Public IPv4 address**.

5.  If SSH times out, update the security group's inbound SSH rule
    (`22`) to **My IP**.

6.  From Windows PowerShell, connect:

    ``` powershell
    ssh -i "D:\agentops-ai.pem" ubuntu@YOUR_PUBLIC_IP
    ```

7.  If PEM permissions fail, run in PowerShell:

    ``` powershell
    icacls "D:\agentops-ai.pem" /inheritance:r
    icacls "D:\agentops-ai.pem" /grant:r "$((whoami)):(R)"
    icacls "D:\agentops-ai.pem" /remove "NT AUTHORITY\Authenticated Users" "BUILTIN\Users"
    ```

### Check and access the deployment

8.  On EC2, check running containers:

    ``` bash
    sudo docker ps
    ```

9.  Open Coolify at `http://YOUR_PUBLIC_IP:8000`.

10. Sign in and open the AgentOps resource.

11. If the EC2 public IP changed, open **Domains** in Coolify.

12. Update the frontend domain with the new IP; retain port `3000`.

13. Update the API domain with the new IP; retain port `8010`.

14. Save the changes and redeploy if Coolify requests it.

15. Open the frontend domain and test the AgentOps login.

16. To inspect a container's logs:

``` bash
sudo docker logs --tail 100 CONTAINER_NAME
```

### Stop the instance

17. In AWS EC2, select the instance and choose **Instance state → Stop
    instance**.
18. Do not choose **Terminate** and do not delete Docker volumes.
19. When starting it again, repeat steps 2--5, then check the containers
    and Coolify deployment (steps 8--15).
20. The application is accessible only while EC2 is running. Data on the
    EBS volume persists when the instance is stopped.

## Operational Notes

-   The EC2 public IPv4 address may change after a stop/start unless an
    Elastic IP is configured.
-   When the IP changes, update the frontend and API domains in Coolify
    before testing the application.
-   Keep SSH (`22`) and the Coolify dashboard (`8000`) restricted to
    trusted IP addresses. Public web traffic should use the configured
    HTTP/HTTPS ports.
-   Keep database backups before performing database restores,
    migrations, or other destructive operations.
-   Never commit `.env` files, API keys, database passwords, or the PEM
    private key to the repository.

## Health Checks and Troubleshooting

-   Check containers: `sudo docker ps`
-   Check application logs: `sudo docker logs --tail 100 CONTAINER_NAME`
-   Check deployment status and environment variables in the AgentOps
    resource in Coolify.
-   If the website is unavailable, verify that EC2 is running,
    containers are healthy, security group rules are correct, and
    Coolify domains point to the current public IP.
