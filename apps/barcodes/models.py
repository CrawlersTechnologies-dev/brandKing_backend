from django.db import models

class BarcodeSequence(models.Model):
    """
    Singleton model to track the last generated barcode number globally.
    """
    last_value = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'barcode_sequence'
        verbose_name = 'Barcode Sequence'
        verbose_name_plural = 'Barcode Sequence'

    @classmethod
    def get_next_value(cls):
        from django.db import transaction
        
        with transaction.atomic():
            # Lock the sequence row
            sequence, created = cls.objects.select_for_update().get_or_create(id=1)
            sequence.last_value += 1
            sequence.save()
            return sequence.last_value
