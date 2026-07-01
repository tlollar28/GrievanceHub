# GrievanceHub Architecture

GrievanceHub is a production-grade, AI-powered union case management platform.

The system is designed as a deployable SaaS application using:

- Next.js, React, TypeScript, and Node.js for the frontend
- FastAPI and Python for the backend
- PostgreSQL with pgvector for relational data and semantic search
- LangChain, PyTorch, TensorFlow, and Hugging Face for AI/ML workflows
- Redis and Celery for background jobs
- Docker, Kubernetes, Terraform, and AWS for deployment
- GitHub Actions for CI/CD

## Core Purpose

GrievanceHub helps union representatives manage grievance cases, analyze uploaded evidence, search official sources, generate reports, and interact with an AI assistant grounded in authoritative labor documents.

## Permanent Architecture Rule

This project is not being built as a temporary prototype.

All major implementation decisions should support the long-term production version of GrievanceHub.