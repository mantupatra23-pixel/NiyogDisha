import asyncio
from app.core.database import AsyncSessionLocal
from app.models.models import JobCategory, Organization, Qualification, State


async def seed():
    async with AsyncSessionLocal() as db:
        # 1. States
        states_data = [
            {"name": "All India / Central", "code": "AI", "slug": "all-india"},
            {"name": "Odisha", "code": "OD", "slug": "odisha"},
            {"name": "Delhi", "code": "DL", "slug": "delhi"},
            {"name": "Bihar", "code": "BR", "slug": "bihar"},
            {"name": "Uttar Pradesh", "code": "UP", "slug": "uttar-pradesh"},
        ]
        for s in states_data:
            db.add(State(**s))

        # 2. Categories
        categories = [
            {"name": "UPSC", "slug": "upsc", "description": "Union Public Service Commission"},
            {"name": "SSC", "slug": "ssc", "description": "Staff Selection Commission"},
            {"name": "Railway / RRB", "slug": "railway", "description": "Railway Recruitment Board"},
            {"name": "Banking / IBPS / SBI", "slug": "banking", "description": "Banking & Financial Institutes"},
            {"name": "Defence & Police", "slug": "defence-police", "description": "Army, Navy, Airforce & Police"},
            {"name": "Teaching", "slug": "teaching", "description": "Teacher Eligibility & University Vacancies"},
        ]
        for c in categories:
            db.add(JobCategory(**c))

        # 3. Qualifications
        quals = [
            {"name": "10th Pass (Matric)", "slug": "10th-pass"},
            {"name": "12th Pass (Intermediate)", "slug": "12th-pass"},
            {"name": "ITI / Diploma", "slug": "diploma-iti"},
            {"name": "Graduate (Any Stream)", "slug": "graduate"},
            {"name": "B.Tech / B.E. / Engineering", "slug": "engineering"},
            {"name": "Post Graduate", "slug": "post-graduate"},
        ]
        for q in quals:
            db.add(Qualification(**q))

        # 4. Standard Organizations
        orgs = [
            {
                "name": "Union Public Service Commission",
                "short_name": "UPSC",
                "slug": "upsc",
                "official_website": "https://upsc.gov.in",
                "org_type": "CENTRAL",
            },
            {
                "name": "Staff Selection Commission",
                "short_name": "SSC",
                "slug": "ssc",
                "official_website": "https://ssc.gov.in",
                "org_type": "CENTRAL",
            },
            {
                "name": "Railway Recruitment Control Board",
                "short_name": "RRB",
                "slug": "rrb",
                "official_website": "https://indianrailways.gov.in",
                "org_type": "CENTRAL",
            },
            {
                "name": "Odisha Public Service Commission",
                "short_name": "OPSC",
                "slug": "opsc",
                "official_website": "https://opsc.gov.in",
                "org_type": "STATE",
            },
        ]
        for org in orgs:
            db.add(Organization(**org))

        await db.commit()
        print("✅ Base master data (States, Categories, Qualifications, Organizations) seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
