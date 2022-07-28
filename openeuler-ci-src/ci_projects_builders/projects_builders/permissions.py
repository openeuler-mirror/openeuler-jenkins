from rest_framework import permissions
  

class HookPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        data = request.data
        hook_name = data.get('hook_name', '')
        action = data.get('action', '')
        if hook_name == 'merge_request_hooks' and action == 'merge':
            return True
