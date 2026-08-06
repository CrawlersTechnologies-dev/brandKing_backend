import os
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def validate_file_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
    if ext not in valid_extensions:
        raise ValidationError(
            _('Unsupported file extension. Allowed extensions are: pdf, jpg, jpeg, png.')
        )

def validate_file_size(value):
    limit = 5 * 1024 * 1024 # 5 MB
    if value.size > limit:
        raise ValidationError(
            _('File size exceeds the 5MB limit.')
        )

def validate_profile_photo_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png']
    if ext not in valid_extensions:
        raise ValidationError(
            _('Unsupported profile photo extension. Allowed extensions are: jpg, jpeg, png.')
        )
