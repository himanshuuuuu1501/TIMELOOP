
import json
import secrets

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

User = get_user_model()


def get_user_data(user):
    return {
        "authenticated": True,
        "id": user.id,
        "username": user.get_username(),
        "email": user.email,
        "is_admin": user.is_staff,
    }


@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_GET
def current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False}, status=200)

    return JsonResponse(get_user_data(request.user))


@require_POST
def register(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    admin_code = data.get("admin_code", "")

    if not username or not email or not isinstance(password, str):
        return JsonResponse(
            {"error": "Username, email and password are required."},
            status=400,
        )

    if len(password) < 8:
        return JsonResponse(
            {"error": "Password must contain at least 8 characters."},
            status=400,
        )

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"error": "Username already exists."}, status=400)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"error": "Email already registered."}, status=400)

    configured_code = getattr(
        settings,
        "TIMELOOP_ADMIN_ACTIVATION_CODE",
        "",
    )

    if admin_code:
        if (
            not isinstance(admin_code, str)
            or not configured_code
            or not secrets.compare_digest(admin_code, configured_code)
        ):
            return JsonResponse(
                {"error": "Invalid admin activation code."},
                status=403,
            )

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
    )

    if admin_code:
        user.is_staff = True
        user.save(update_fields=["is_staff"])

    login(request, user)
    return JsonResponse(get_user_data(user), status=201)


@require_POST
def login_user(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    username = str(data.get("username", "")).strip()
    password = data.get("password", "")

    if not username or not isinstance(password, str) or not password:
        return JsonResponse(
            {"error": "Username and password are required."},
            status=400,
        )

    user_record = User.objects.filter(username__iexact=username).first()
    canonical_username = (
        user_record.get_username() if user_record else username
    )

    user = authenticate(
        request,
        username=canonical_username,
        password=password,
    )

    if user is None:
        return JsonResponse(
            {"error": "Invalid username or password."},
            status=400,
        )

    login(request, user)
    return JsonResponse(get_user_data(user))


@require_POST
def logout_user(request):
    logout(request)
    return JsonResponse({"authenticated": False})
