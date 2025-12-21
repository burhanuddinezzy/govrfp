import time

def is_captcha_in_html(html):
    markers = [
        'id="recaptcha-anchor-label"',
    ]
    extra_signals = [
        'Im not a robot',
        'Our systems have detected unusual traffic from your computer network'
        #'g-recaptcha',        # common attribute for reCAPTCHA
        #'recaptcha',          # generic string
        ##'class="grecaptcha"', # other naming
        #'data-sitekey'        # reCAPTCHA sitekey attribute
    ]
    #for m in markers:
     #   if m in html:
      #      return True
    for s in extra_signals:
        if s in html:
            return True
    return False

def check_for_captcha(driver, poll_interval=20):
    try:
        html = driver.page_source or ""
    except Exception as e:
        print(f"[WARN] Could not get page source to check captcha: {e}")
        return

    if not is_captcha_in_html(html):
        return

    print(
        "[ACTION REQUIRED]\n"
        "- Solve captcha in browser if present\n"
        "- OR press ENTER here to continue anyway\n"
        "- OR type 'skip' and press ENTER to skip this page\n"
    )

    while True:
        # Manual override
        user_input = input(
            f"[WAITING] Press ENTER to resume, 'skip' to skip page, "
            f"or wait {poll_interval}s for auto-check: "
        ).strip().lower()

        if user_input == "":
            print("[MANUAL OVERRIDE] Resuming scraping.")
            time.sleep(1)
            return

        if user_input == "skip":
            print("[MANUAL OVERRIDE] Skipping current page.")
            raise RuntimeError("User chose to skip page due to captcha.")

        # Auto-check path
        time.sleep(poll_interval)
        try:
            html = driver.page_source or ""
        except Exception as e:
            print(f"[WARN] Could not refresh page source: {e}")
            continue

        if not is_captcha_in_html(html):
            print("[CAPTCHA CLEARED] Marker no longer detected. Resuming.")
            time.sleep(1)
            return

        print("[STILL BLOCKED] Marker still present.")
