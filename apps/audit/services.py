from apps.audit.models import AuditLog

class AuditService:
    @staticmethod
    def log(user, action, module, object_type, object_id, old_value=None, new_value=None):
        role = user.role if user else None
        branch = user.branch if user else None
        
        import json
        from django.core.serializers.json import DjangoJSONEncoder

        if old_value is not None:
            old_value = json.loads(json.dumps(old_value, cls=DjangoJSONEncoder))
        if new_value is not None:
            new_value = json.loads(json.dumps(new_value, cls=DjangoJSONEncoder))

        AuditLog.objects.create(
            user=user,
            role=role,
            branch=branch,
            action=action,
            module=module,
            object_type=object_type,
            object_id=str(object_id),
            old_value=old_value,
            new_value=new_value
        )
