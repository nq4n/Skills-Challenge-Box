# Skills Challenge Box — Demo (Flask + HTML/CSS/JS)

Style-only demo of the QR → Skill → Quiz → Result flow. No real DB/auth yet.

## Run
```bash
cd skills_challenge_box
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py  # then open http://127.0.0.1:5000
```

## Try it
- Home: `/`
- Switch user:
  - `/login/admin`
  - `/login/student_1`
  - `/login/student_2`
- Dashboard: `/dashboard`
- Example skill via QR URL: `/skill/communication/COMM-0001-A1B2`

## Notes
- All “one-time scan”, points, and badges are simulated.
- Clear TODOs indicate where MySQL integration will go later.
