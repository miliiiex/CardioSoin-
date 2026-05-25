from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailOrUsernameBackend(ModelBackend):
    """
    Connexion avec e-mail ou nom d'utilisateur.
    Si la chaîne contient '@', recherche par e-mail (un seul compte par e-mail attendu).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get("email") or kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None

        username = str(username).strip()
        user = None

        if "@" in username:
            qs = UserModel.objects.filter(email__iexact=username)
            if qs.count() == 1:
                user = qs.first()
            elif qs.count() > 1:
                return None
            else:
                # Aucun email correspondant : souvent l’utilisateur a été créé avec
                # username "admin@test.com" (autorisé par Django) et un autre email.
                try:
                    user = UserModel.objects.get(username__iexact=username)
                except UserModel.DoesNotExist:
                    return None
        else:
            try:
                user = UserModel.objects.get(username__iexact=username)
            except UserModel.DoesNotExist:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
