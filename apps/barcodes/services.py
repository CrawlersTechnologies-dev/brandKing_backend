import uuid
import string
import random

class BarcodeService:
    @staticmethod
    def generate_proprietary_barcode(branch_code=None):
        """
        Generates a unique proprietary barcode.
        Format: BK-[BranchCode]-[8-char-alphanumeric]
        If no branch code is provided, defaults to BK-GEN-[8-char-alphanumeric]
        """
        branch_prefix = branch_code.upper() if branch_code else "GEN"
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"BK-{branch_prefix}-{random_suffix}"
