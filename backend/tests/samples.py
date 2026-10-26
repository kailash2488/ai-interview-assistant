"""Five synthetic resumes (different layouts/headings) plus one JD, used for parser tests."""

RESUMES = {
    "backend_dev": """Asha Verma
asha.verma@example.com | +91 90000 00001

SUMMARY
Backend engineer with 5 years of experience building Python APIs.

EXPERIENCE
Senior Software Engineer, Acme Corp (2021 - Present)
• Built FastAPI microservices handling 2M requests per day
• Reduced p95 latency by 40% through query tuning

Software Engineer, Beta Labs (2019 - 2021)
• Developed Django REST APIs and Celery workers

PROJECTS
Interview Bot - Python, LangChain, Qdrant
• Built a RAG chatbot over internal documents

SKILLS
Python, FastAPI, Django, PostgreSQL, Docker, AWS

EDUCATION
B.Tech Computer Science, 2019
""",
    "ml_engineer": """Rohan Mehta
rohan@example.com

Professional Summary
Machine learning engineer focused on NLP and LLM applications.

Work Experience
ML Engineer - Gamma AI (2022 - Present)
- Fine-tuned transformer models for classification
- Deployed models with Docker and Kubernetes

Technical Skills:
PyTorch, scikit-learn, Hugging Face, SQL, MLflow

Education
M.Sc. Data Science, 2022

Certifications
AWS Certified Machine Learning Specialty
""",
    "fresher": """PRIYA NAIR
priya.nair@example.com

OBJECTIVE
Fresher looking for a software engineering role in AI.

EDUCATION
B.E. Information Technology, 2025, CGPA 8.7

PROJECTS
Resume Parser - Python, spaCy
- Extracted skills from resumes with 90% accuracy
Chat App - React, Node.js
- Real-time chat using WebSockets

SKILLS
Python, JavaScript, React, SQL, Git

ACHIEVEMENTS
Winner, college hackathon 2024
""",
    "devops": """Karan Singh
karan@example.com

EXPERIENCE
DevOps Engineer, Delta Systems (2018 - Present)
* Managed CI/CD pipelines with GitHub Actions and Jenkins
* Provisioned infrastructure with Terraform on AWS

SKILLS
Linux, Docker, Kubernetes, Terraform, Ansible, Prometheus

EDUCATION
B.Sc. Computer Science, 2018
""",
    "no_headings": """Meera Iyer is a full stack developer with four years of experience.
She has worked with React, TypeScript, Node.js and PostgreSQL across
several startups, shipping customer facing dashboards and internal tools.
Contact: meera@example.com
""",
}

JD = """Senior Python Developer

About
We are building an AI platform for hiring.

Responsibilities
- Design and build FastAPI services
- Work with LLM pipelines and vector databases

Requirements
- 4+ years of Python
- Experience with PostgreSQL and Docker

Nice to have
- Experience with LangChain
"""
