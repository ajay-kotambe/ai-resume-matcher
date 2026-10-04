"""Generate realistic multi-page PDF resumes for end-to-end testing.

Usage:  python scripts/make_test_pdfs.py
Output: backend/samples/*.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
SAMPLES.mkdir(exist_ok=True)


def _page(doc: pymupdf.Document, text: str, width: int = 42) -> None:
    """Render a block of monospace text onto a new page."""

    page = doc.new_page()
    lines = text.split("\n")
    y = 60
    for line in lines:
        if y > 780:
            page = doc.new_page()
            y = 60
        page.insert_text((50, y), line, fontsize=9, fontname="cour", color=(0, 0, 0))
        y += 13


RESUMES: dict[str, str] = {
    # Strong match: full-stack, deep, all required skills present.
    "rahul_sharma_strong.pdf": """RAHUL SHARMA
Senior Full Stack Engineer
rahul.sharma@gmail.com | +91 98765 43210 | Bangalore, India
SUMMARY
Senior full stack engineer with 6 years of experience building and scaling
production web applications. Comfortable owning features end to end.

TECHNICAL SKILLS
Languages: JavaScript, TypeScript, Python, SQL
Frontend: React, Redux, HTML, CSS, Tailwind CSS
Backend: Node.js, Express, REST API, GraphQL
Database: PostgreSQL, MongoDB, Redis
Cloud & DevOps: AWS, Docker, Kubernetes, CI/CD, Git
Data: Machine Learning, pandas

EXPERIENCE
Senior Software Engineer | Flipkart | Mar 2021 - Present
- Built a React and TypeScript dashboard used by 40000 monthly users.
- Designed REST API services in Node.js and Express handling 2000 requests per second.
- Migrated PostgreSQL reporting queries, cutting p95 latency by 60 percent.
- Ran services on AWS with Docker and Kubernetes in a CI/CD pipeline managed by GitHub Actions.
- Mentored four junior engineers and ran design reviews.

Software Engineer | Zoho | Jul 2018 - Feb 2021
- Developed React interfaces and Redux state management for a B2B dashboard.
- Built Python microservices exposing REST API endpoints.
- Implemented unit testing with pytest raising coverage to 85 percent.

EDUCATION
B.Tech Computer Science | Anna University | 2018

CERTIFICATIONS
AWS Certified Solutions Architect - Associate
Certified Kubernetes Application Developer

PROJECTS
Shopify Recommendation Engine | React, Node.js, PostgreSQL, Machine Learning
- Built a product recommendation feature using collaborative filtering in Python.""",
    # Good match: solid but missing Docker/Kubernetes, less experience.
    "priya_patil_mid.pdf": """PRIYA PATIL
Full Stack Developer
priya.patil@gmail.com | +91 90000 12345 | Pune, India
SUMMARY
Full stack developer with 4 years of experience delivering customer facing
products and internal tools.

TECHNICAL SKILLS
Languages: JavaScript, TypeScript, Python
Frontend: React, Next.js, HTML, CSS
Backend: Node.js, Express, REST API
Database: PostgreSQL, MySQL
Tools: Git, Docker, Agile, Jira

EXPERIENCE
Full Stack Developer | Persistent Systems | Jun 2021 - Present
- Developed React and Next.js interfaces for enterprise clients.
- Built and maintained Node.js and Express REST API services.
- Wrote Python scripts for data processing and reporting.
- Used Docker for local development and continuous integration.

Software Engineer | Cognizant | Aug 2019 - May 2021
- Built internal dashboards in React with TypeScript.
- Worked with PostgreSQL and MySQL for reporting requirements.

EDUCATION
B.E Computer Engineering | University of Pune | 2019

PROJECTS
Inventory Dashboard | React, Node.js, PostgreSQL
Task Scheduler | Python, MySQL""",
    # Poor match: front-end only, no backend/database/cloud skills.
    "amit_joshi_poor.pdf": """AMIT JOSHI
Frontend Developer
amit.joshi@gmail.com | +91 81234 56789 | Jaipur, India
SUMMARY
Frontend developer focused on accessible, responsive user interfaces.

TECHNICAL SKILLS
Languages: HTML, CSS, JavaScript
Frontend: React, jQuery, Sass, Figma
Tools: Git

EXPERIENCE
Frontend Developer | Local Startup | Jan 2022 - Present
- Built responsive marketing pages and component libraries in React.
- Improved Lighthouse accessibility scores from 72 to 96.
- Worked with designers in Figma to implement design systems.

EDUCATION
B.Com | University of Rajasthan | 2021

PROJECTS
Portfolio Website | HTML, CSS, JavaScript
Photography Gallery | React, Sass""",
    # Sparse resume: very little information, one skill mentioned in passing.
    "neha_sharma_minimal.pdf": """NEHA SHARMA
neha.sharma@outlook.com

Looking for a job in software development.

SKILLS
Basic knowledge of Python.

EDUCATION
B.Com""",
}


def build() -> list[Path]:
    written: list[Path] = []
    for filename, text in RESUMES.items():
        doc = pymupdf.open()
        _page(doc, text)
        target = SAMPLES / filename
        doc.save(target)
        doc.close()
        written.append(target)
        print(f"wrote {target.name} ({target.stat().st_size} bytes)")
    return written


def build_empty_pdf() -> Path:
    """A valid PDF with zero extractable text (simulates a scanned image)."""

    doc = pymupdf.open()
    page = doc.new_page()
    # Draw a filled rectangle: visible content, no text layer.
    page.draw_rect(pymupdf.Rect(50, 50, 550, 750), color=(0.85, 0.85, 0.85), fill=(0.85, 0.85, 0.85))
    target = SAMPLES / "empty_scan.pdf"
    doc.save(target)
    doc.close()
    print(f"wrote {target.name} ({target.stat().st_size} bytes)")
    return target


if __name__ == "__main__":
    build()
    build_empty_pdf()
    print(f"\n{len(RESUMES) + 1} sample files in {SAMPLES}")
    sys.exit(0)