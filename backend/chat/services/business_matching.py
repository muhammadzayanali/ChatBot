"""
Business matching: geographic (ZIP/county/radius), sponsored first, rotation, 3–5 results, "see more", "closest available".
Service categories are the main anchor. Tracks impressions and supports WhatsApp contact.
Uses MongoDB (BraeloDB) when USE_MONGO is True.
"""
from django.db import transaction
from django.db.models import F


def _distance_miles(lat1, lon1, lat2, lon2):
    """Return distance in miles. Uses geopy if available, else None."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    try:
        from geopy.distance import geodesic
        return round(geodesic((float(lat1), float(lon1)), (float(lat2), float(lon2))).miles, 1)
    except Exception:
        return None


def _get_top_businesses_mongo(
    category: str = None,
    subcategory: str = None,
    state: str = None,
    city: str = None,
    county: str = None,
    zip_code: str = None,
    user_lat=None,
    user_lon=None,
    language: str = None,
    limit: int = None,
    external_id: str = None,
    session_id: str = None,
) -> dict:
    """Read businesses from MongoDB (BraeloDB), rank, update impressions_used. Same return shape as get_top_businesses."""
    from django.conf import settings

    if limit is None:
        limit = getattr(settings, "MAX_BUSINESS_RESULTS", 5)
    radius_miles = getattr(settings, "BUSINESS_RADIUS_MILES", 25)
    radius_fallback = getattr(settings, "BUSINESS_RADIUS_FALLBACK_MILES", 50)
    try:
        from chat.mongo_db import get_db
        db = get_db()
        ad_pkgs = {p["name"]: p for p in db.ad_packages.find({})}
        q = {
            "is_active": True,
            "is_banned": {"$ne": True},
            "$expr": {"$lt": ["$impressions_used", "$impression_cap"]},
        }
        if category:
            q["category"] = {"$regex": category, "$options": "i"}
        if subcategory:
            q["subcategory"] = {"$regex": subcategory, "$options": "i"}
        if state:
            q["state"] = {"$regex": state, "$options": "i"}
        if city:
            q["city"] = {"$regex": city, "$options": "i"}
        if county:
            q["county"] = {"$regex": county, "$options": "i"}
        if zip_code:
            q["zip_code"] = zip_code
        if language:
            q["languages"] = {"$regex": language, "$options": "i"}
        all_rows = list(db.businesses.find(q))
    except Exception:
        return {"businesses": [], "see_more": False, "location_note": None}

    def priority_and_distance(b):
        pkg_priority = 0
        ad_name = b.get("ad_package_name")
        if ad_name and ad_name in ad_pkgs:
            pkg_priority = ad_pkgs[ad_name].get("priority") or 0
        dist = None
        if user_lat is not None and user_lon is not None and b.get("latitude") is not None and b.get("longitude") is not None:
            dist = _distance_miles(user_lat, user_lon, b["latitude"], b["longitude"])
        remaining = (b.get("impression_cap") or 0) - (b.get("impressions_used") or 0)
        return (pkg_priority, dist, b.get("rotation_index", 0), -remaining)

    def sort_key(b):
        pkg_priority, dist, rot, rem = priority_and_distance(b)
        dist_val = dist if dist is not None else 9999
        return (-pkg_priority, dist_val, rot, rem)

    all_rows.sort(key=sort_key)

    within_primary = []
    within_fallback = []
    for b in all_rows:
        dist = None
        if user_lat is not None and user_lon is not None and b.get("latitude") is not None and b.get("longitude") is not None:
            dist = _distance_miles(user_lat, user_lon, b["latitude"], b["longitude"])
        if dist is not None:
            if dist <= radius_miles:
                within_primary.append((b, dist))
            elif dist <= radius_fallback:
                within_fallback.append((b, dist))
        else:
            within_primary.append((b, None))

    if within_primary:
        selected_pairs = within_primary[:limit]
        location_note = None
    else:
        selected_pairs = within_fallback[:limit] if within_fallback else [(b, None) for b in all_rows[:limit]]
        location_note = "No exact matches in your area. Here are the closest available options."

    total_available = len(within_primary) or len(within_fallback) or len(all_rows)
    see_more = total_available > limit

    out_list = []
    for b, dist in selected_pairs:
        bid = str(b["_id"])
        out_list.append({
            "id": bid,
            "name": b.get("name", ""),
            "category": b.get("category"),
            "subcategory": b.get("subcategory"),
            "state": b.get("state"),
            "city": b.get("city"),
            "county": b.get("county"),
            "zip_code": b.get("zip_code"),
            "languages": b.get("languages"),
            "contact_info": b.get("contact_info"),
            "whatsapp_url": b.get("whatsapp_url") or "",
            "distance_miles": dist,
            "is_sponsored": bool(b.get("ad_package_name")),
        })
        try:
            db.businesses.update_one(
                {"_id": b["_id"]},
                {"$inc": {"impressions_used": 1}},
            )
            db.impressions_log.insert_one({
                "business_id": bid,
                "external_id": external_id,
                "session_id": session_id,
                "created_at": __import__("datetime").datetime.utcnow(),
            })
        except Exception:
            pass

    return {"businesses": out_list, "see_more": see_more, "location_note": location_note}


def get_top_businesses(
    category: str = None,
    subcategory: str = None,
    state: str = None,
    city: str = None,
    county: str = None,
    zip_code: str = None,
    user_lat=None,
    user_lon=None,
    language: str = None,
    limit: int = None,
    external_id: str = None,
    session_id: str = None,
) -> dict:
    """
    Return 3–5 businesses matching filters. Sponsored first, then by distance/rotation.
    Returns dict: { "businesses": [...], "see_more": bool, "location_note": str }.
    If no exact match in area, returns closest available and sets location_note.
    """
    from django.conf import settings
    if getattr(settings, "USE_MONGO", False):
        return _get_top_businesses_mongo(
            category=category, subcategory=subcategory, state=state, city=city,
            county=county, zip_code=zip_code, user_lat=user_lat, user_lon=user_lon,
            language=language, limit=limit, external_id=external_id, session_id=session_id,
        )

    from chat.models import Business, AdPackage, ImpressionsLog

    if limit is None:
        limit = getattr(settings, "MAX_BUSINESS_RESULTS", 5)
    radius_miles = getattr(settings, "BUSINESS_RADIUS_MILES", 25)
    radius_fallback = getattr(settings, "BUSINESS_RADIUS_FALLBACK_MILES", 50)
    min_results = getattr(settings, "MIN_BUSINESS_RESULTS", 3)

    try:
        qs = Business.objects.filter(
            is_active=True,
            is_banned=False,
        ).filter(impressions_used__lt=F("impression_cap"))
        if category:
            qs = qs.filter(category__icontains=category)
        if subcategory:
            qs = qs.filter(subcategory__icontains=subcategory)
        if state:
            qs = qs.filter(state__icontains=state)
        if city:
            qs = qs.filter(city__icontains=city)
        if county:
            qs = qs.filter(county__icontains=county)
        if zip_code:
            qs = qs.filter(zip_code=zip_code)
        if language:
            qs = qs.filter(languages__icontains=language)

        all_rows = list(qs)

        # Attach distance and sponsored priority
        def priority_and_distance(b):
            pkg_priority = 0
            if b.ad_package_id:
                try:
                    pkg = AdPackage.objects.get(pk=b.ad_package_id)
                    pkg_priority = pkg.priority or 0
                except AdPackage.DoesNotExist:
                    pass
            dist = None
            if user_lat is not None and user_lon is not None and b.latitude is not None and b.longitude is not None:
                dist = _distance_miles(user_lat, user_lon, b.latitude, b.longitude)
            remaining = (b.impression_cap or 0) - (b.impressions_used or 0)
            return (pkg_priority, dist, b.rotation_index, -remaining)

        # Sort: sponsored first, then by distance (closer first), then rotation_index, then remaining impressions
        def sort_key(b):
            pkg_priority, dist, rot, rem = priority_and_distance(b)
            dist_val = dist if dist is not None else 9999
            return (-pkg_priority, dist_val, rot, rem)

        all_rows.sort(key=sort_key)

        # Apply radius: prefer within radius_miles, else include up to radius_fallback and set location_note
        within_primary = []
        within_fallback = []
        for b in all_rows:
            dist = None
            if user_lat is not None and user_lon is not None and b.latitude is not None and b.longitude is not None:
                dist = _distance_miles(user_lat, user_lon, b.latitude, b.longitude)
            if dist is not None:
                if dist <= radius_miles:
                    within_primary.append((b, dist))
                elif dist <= radius_fallback:
                    within_fallback.append((b, dist))
            else:
                within_primary.append((b, None))

        if within_primary:
            selected_pairs = within_primary[:limit]
            location_note = None
        else:
            selected_pairs = within_fallback[:limit] if within_fallback else [(b, None) for b in all_rows[:limit]]
            location_note = "No exact matches in your area. Here are the closest available options."

        total_available = len(within_primary) or len(within_fallback) or len(all_rows)
        see_more = total_available > limit

        out_list = []
        with transaction.atomic():
            for b, dist in selected_pairs:
                out_list.append({
                    "id": b.id,
                    "name": b.name,
                    "category": b.category,
                    "subcategory": b.subcategory,
                    "state": b.state,
                    "city": b.city,
                    "county": getattr(b, "county", None),
                    "zip_code": getattr(b, "zip_code", None),
                    "languages": b.languages,
                    "contact_info": b.contact_info,
                    "whatsapp_url": getattr(b, "whatsapp_url", None) or "",
                    "distance_miles": dist,
                    "is_sponsored": bool(b.ad_package_id),
                })
                b.impressions_used = (b.impressions_used or 0) + 1
                b.save(update_fields=["impressions_used"])
                ImpressionsLog.objects.create(
                    business=b,
                    external_id=external_id,
                    session_id=session_id,
                )

        return {
            "businesses": out_list,
            "see_more": see_more,
            "location_note": location_note,
        }
    except Exception:
        return {"businesses": [], "see_more": False, "location_note": None}
