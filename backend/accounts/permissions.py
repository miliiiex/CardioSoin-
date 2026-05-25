def is_patient(u):
    return u.is_authenticated and getattr(u, "role", None) == "patient"


def is_doctor(u):
    return u.is_authenticated and getattr(u, "role", None) == "doctor"


def is_secretary(u):
    return u.is_authenticated and getattr(u, "role", None) == "secretary"


def is_doctor_or_secretary(u):
    return is_doctor(u) or is_secretary(u)
