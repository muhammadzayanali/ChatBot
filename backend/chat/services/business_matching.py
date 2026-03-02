"""
Business matching: query by category/state/city/language, prioritize sponsored, log impressions.
Ported from Flask — uses Django ORM instead of SQLAlchemy.
"""
from django.db import transaction
from django.db.models import F


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
    from chat.models import Business, AdPackage, ImpressionsLog

    try:
        qs = Business.objects.filter(impressions_used__lt=F("impression_cap"))
        if category:
            qs = qs.filter(category__icontains=category)
        if subcategory:
            qs = qs.filter(subcategory__icontains=subcategory)
        if state:
            qs = qs.filter(state__icontains=state)
        if city:
            qs = qs.filter(city__icontains=city)
        if language:
            qs = qs.filter(languages__icontains=language)

        all_rows = list(qs)

        # Sort: has ad_package first, then by priority, then by remaining impressions (desc)
        def sort_key(b):
            pkg_priority = 0
            if b.ad_package_id:
                try:
                    pkg = AdPackage.objects.get(pk=b.ad_package_id)
                    pkg_priority = pkg.priority or 0
                except AdPackage.DoesNotExist:
                    pass
            remaining = (b.impression_cap or 0) - (b.impressions_used or 0)
            return (-pkg_priority, -remaining)

        all_rows.sort(key=sort_key)
        selected = all_rows[:limit]

        out = []
        with transaction.atomic():
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
                b.save(update_fields=["impressions_used"])
                ImpressionsLog.objects.create(
                    business=b,
                    external_id=external_id,
                    session_id=session_id,
                )
        return out
    except Exception:
        return []
