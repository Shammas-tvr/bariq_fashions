from django.shortcuts import redirect
from django.contrib.auth import logout



class BlockedUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, 'is_blocked', False):
            logout(request)
            return redirect('blocked_page')  # You can create a "you are blocked" page
        return self.get_response(request)