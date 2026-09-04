import re

SKILL_ALIASES = {
    "python": ["python"], "java": ["java"], "javascript": ["javascript", "java script", "js"],
    "html": ["html", "html5"], "css": ["css", "css3"], "react": ["react", "reactjs", "react.js"],
    "node.js": ["node.js", "nodejs", "node js"], "sql": ["sql", "mysql", "sqlite", "postgresql", "postgres"],
    "mongodb": ["mongodb", "mongo db", "mongo"], "flask": ["flask"], "django": ["django"],
    "c": ["c programming", "c language"], "c++": ["c++"], "c#": ["c#", "c sharp"], "kotlin": ["kotlin"],
    "git": ["git", "github", "gitlab"], "docker": ["docker"], "linux": ["linux", "ubuntu"],
    "power bi": ["power bi", "powerbi"], "tableau": ["tableau"], "excel": ["excel", "ms excel", "microsoft excel"],
    "machine learning": ["machine learning", "ml"], "data analysis": ["data analysis", "data analytics"],
    "data science": ["data science", "data scientist"], "cybersecurity": ["cybersecurity", "cyber security", "information security"],
    "networking": ["networking", "tcp/ip", "computer networks", "network security"],
    "aws": ["aws", "amazon web services"], "azure": ["azure", "microsoft azure"],
    "communication": ["communication", "presentation", "teamwork"],
}

SECTION_PATTERNS = {
    "contact": r"\b(email|e-mail|phone|mobile|linkedin|github|portfolio)\b|@",
    "summary": r"\b(summary|professional summary|objective|profile|about me)\b",
    "education": r"\b(education|academic|qualification|degree|university|college|bachelor|master)\b",
    "experience": r"\b(experience|employment|work history|internship|internships|professional experience)\b",
    "projects": r"\b(projects|project experience|academic projects|personal projects)\b",
    "skills": r"\b(skills|technical skills|technologies|technical competencies|core skills)\b",
    "certifications": r"\b(certification|certifications|courses|training)\b",
}

ACTION_WORDS = r"\b(achieved|increased|reduced|improved|developed|built|created|designed|implemented|led|managed|optimized|automated|delivered)\b"
QUANTIFIED = r"(?:\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\+?|\b\d+(?:\.\d+)?\s*(?:users|clients|projects|months|years|members))"


def _contains_alias(low, alias):
    alias = alias.lower().strip()
    if not alias:
        return False
    if len(alias) <= 2 and alias.isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", low))
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", low))


def extract_skills(text):
    low = re.sub(r"\s+", " ", text.lower())
    return sorted(skill for skill, aliases in SKILL_ALIASES.items() if any(_contains_alias(low, a) for a in aliases))


def analyze_resume(text):
    if not text or not text.strip():
        raise ValueError("No readable text was extracted from the resume.")
    low = re.sub(r"\s+", " ", text.lower())
    words = re.findall(r"\b[\w+#.-]+\b", text, flags=re.UNICODE)
    word_count = len(words)
    skills = extract_skills(text)
    sections = {name: bool(re.search(pattern, low, re.I)) for name, pattern in SECTION_PATTERNS.items()}
    score = 0
    if word_count >= 150: score += 8
    if word_count >= 300: score += 7
    if word_count >= 500: score += 5
    score += min(len(skills) * 3, 30)
    score += sum(7 for key in ["summary", "education", "experience", "projects", "skills"] if sections[key])
    if sections["contact"]: score += 5
    if sections["certifications"]: score += 3
    if re.search(r"\b(?:19|20)\d{2}\b", text): score += 3
    if re.search(ACTION_WORDS, low, re.I): score += 5
    if re.search(QUANTIFIED, low, re.I): score += 5
    score = max(0, min(score, 100))

    suggestions = []
    if word_count < 150: suggestions.append("Add more relevant details about projects, experience and achievements.")
    elif word_count > 900: suggestions.append("Consider reducing the resume to the most relevant information.")
    if not sections["summary"]: suggestions.append("Add a short professional summary tailored to the target role.")
    if not sections["skills"]: suggestions.append("Create a dedicated Technical Skills section.")
    if not sections["projects"]: suggestions.append("Add 2–4 relevant academic or personal projects with technologies used.")
    if not sections["experience"]: suggestions.append("Add internship/work experience, or describe relevant practical experience.")
    if len(skills) < 5: suggestions.append("Include more job-relevant technical skills that you actually know.")
    if not sections["certifications"]: suggestions.append("Add relevant certifications or courses if available.")
    if not re.search(ACTION_WORDS, low, re.I): suggestions.append("Use action verbs such as developed, implemented, designed and optimized.")
    if not re.search(QUANTIFIED, low, re.I): suggestions.append("Quantify achievements with percentages, numbers, users, projects or time saved where possible.")

    ats = []
    if word_count < 100: ats.append("Resume content is very short for ATS evaluation.")
    if not sections["skills"]: ats.append("No clearly labelled skills section was detected.")
    if not sections["experience"] and not sections["projects"]: ats.append("No experience or project evidence was detected.")
    if re.search(r"[^\x00-\x7F]", text): ats.append("Special/non-ASCII characters were detected; keep formatting simple for maximum ATS compatibility.")
    if not ats: ats.append("No major ATS issues detected by the built-in checker.")

    strengths = []
    if len(skills) >= 5: strengths.append("Good range of technical and professional skills detected.")
    if sections["projects"]: strengths.append("Projects section detected.")
    if sections["education"]: strengths.append("Education section detected.")
    if sections["experience"]: strengths.append("Experience/internship section detected.")
    if sections["contact"]: strengths.append("Contact information detected.")
    if re.search(QUANTIFIED, low, re.I): strengths.append("Quantified achievements or measurable information detected.")
    if re.search(ACTION_WORDS, low, re.I): strengths.append("Strong action-oriented language detected.")

    return {
        "score": score, "word_count": word_count, "skills": skills, "skill_count": len(skills),
        "sections": sections, "section_status": {k: "Detected" if v else "Missing" for k, v in sections.items()},
        "strengths": strengths or ["Resume has a starting structure that can be improved."],
        "suggestions": suggestions or ["Your resume has a solid basic structure. Tailor it to the job description for an even stronger result."],
        "ats_issues": ats,
    }
