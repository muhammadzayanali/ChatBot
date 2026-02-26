"""
Business matching: query by category/state/city/language, prioritize sponsored, log impressions.
"""
from database.models import Business, AdPackage, ImpressionsLog, SessionLocal


def get_top_businesses(
    category: str = None,
    subcategory: str = None,
    state: str = None,
    city: str = None,
    language: str = None,
    limit: int = 5,
    external_id: str = None,
    session_id: str = None,
) -> list:
    """
    Return up to `limit` businesses matching filters. Sponsored (with ad_package) first, by priority and remaining impressions.
    Deduct impression and log to impressions_log for each returned business.
    """
    db = SessionLocal()
    try:
        q = db.query(Business).filter(Business.impressions_used < Business.impression_cap)
        if category:
            q = q.filter(Business.category.ilike(f"%{category}%"))
        if subcategory:
            q = q.filter(Business.subcategory.ilike(f"%{subcategory}%"))
        if state:
            q = q.filter(Business.state.ilike(f"%{state}%"))
        if city:
            q = q.filter(Business.city.ilike(f"%{city}%"))
        if language:
            q = q.filter(Business.languages.ilike(f"%{language}%"))

        all_rows = q.all()
        # Sort: has ad_package first, then by priority, then by remaining impressions (desc)
        def sort_key(b):
            pkg_priority = 0
            if b.ad_package_id:
                pkg = db.query(AdPackage).get(b.ad_package_id)
                if pkg:
                    pkg_priority = pkg.priority or 0
            remaining = (b.impression_cap or 0) - (b.impressions_used or 0)
            return (-pkg_priority, -remaining)

        all_rows.sort(key=sort_key)
        selected = all_rows[:limit]

        out = []
        for b in selected:
            out.append({
                "id": b.id,
                "name": b.name,
                "category": b.category,
                "subcategory": b.subcategory,
                "state": b.state,
                "city": b.city,
                "languages": b.languages,
                "contact_info": b.contact_info,
            })
            # Deduct impression and log
            b.impressions_used = (b.impressions_used or 0) + 1
            log = ImpressionsLog(
                business_id=b.id,
                external_id=external_id,
                session_id=session_id,
            )
            db.add(log)
        db.commit()
        return out
    except Exception:
        db.rollback()
        return []
    finally:
        db.close()
