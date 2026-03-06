from app.router.smart_router import SmartRouter

router = SmartRouter()

result = router.route("send email to tonyniswin@gmail.com about test message")

print(result)
