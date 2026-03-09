import re


def validate_name(name: str) -> bool:
    """Имя/фамилия: только буквы (включая кириллицу), 2-50 символов."""
    return bool(re.match(r"^[a-zA-Zа-яА-ЯёЁčšžřďťňůúýáéíóěČŠŽŘĎŤŇŮÚÝÁÉÍÓĚ]{2,50}$", name))


def validate_phone(phone: str) -> bool:
    """Телефон: опциональный +, затем 9-15 цифр."""
    return bool(re.match(r"^\+?\d{9,15}$", phone))


def normalize_phone(phone: str) -> str:
    """Оставляет только цифры и ведущий +."""
    digits = re.sub(r"[^\d+]", "", phone)
    return digits
