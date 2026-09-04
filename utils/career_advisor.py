ROLE_SKILLS = {
    "Frontend Developer": ["html","css","javascript","react","git"],
    "Backend Developer": ["python","flask","sql","git","docker"],
    "Full Stack Developer": ["html","css","javascript","react","node.js","sql","git"],
    "Python Developer": ["python","sql","git","flask","django"],
    "Data Analyst": ["python","sql","excel","power bi","data analysis"],
    "Data Scientist": ["python","sql","machine learning","data analysis"],
    "Cybersecurity Analyst": ["cybersecurity","networking","python","linux","git"],
    "Database Developer": ["sql","mysql","mongodb","python"],
    "Android Developer": ["kotlin","java","git"],
}

def career_recommendations(skills, text=""):
    have = set(s.lower() for s in skills)
    results = []
    for role, required in ROLE_SKILLS.items():
        matched = [s for s in required if s in have]
        missing = [s for s in required if s not in have]
        percent = round(len(matched) / len(required) * 100)
        results.append({"role": role, "match": percent, "matched": matched, "missing": missing})
    return sorted(results, key=lambda x: x["match"], reverse=True)
