# AttendAI — AI-Driven Attendance System
### Facial Recognition · Session Token · Geo-Fencing

A complete, self-contained web application for classroom attendance that
verifies a student is **who they say they are**, **physically present**,
and **checking in during a valid, time-bound window** — before a single
attendance mark is recorded.

This implements the pipeline from the project's system design:

```
Student → Camera/Device → Data Capture (Face + Location)
        → [Facial Recognition] + [Session Token] + [Geo-Fencing]
        → Attendance Validation → Attendance Database → Teacher/Admin Panel
```

---

## 1. Features

**Account security**

- **Email verification via OTP** — registration is a two-step process:
  submit your details, then enter a 6-digit code emailed to you before
  the account is actually created. No user account exists in the
  database until the code is verified, so every account is guaranteed to
  have a real, reachable email.
- **Forgot password (OTP-based reset)** — a "Forgot password?" link on
  the login page walks through: enter your email → enter the code we
  send you → set a new password. The reset code is single-use and
  expires after 10 minutes.
- **Password requirements, enforced both live and server-side** — every
  password (at registration and at reset) must have:
  - at least 7 characters
  - at least one uppercase letter
  - at least one number
  - at least one special character

  A live checklist under the password field ticks off each requirement
  as you type, so you know exactly what's missing before you submit —
  but the server always re-checks these rules too, since client-side JS
  can be bypassed.
- **No email server required to test the app** — if `SMTP_USER` /
  `SMTP_PASSWORD` aren't configured, OTP codes are printed to the
  server's terminal (and shown directly in the UI as a "dev mode"
  banner) instead of being emailed, so registration and password reset
  work immediately without any setup. See section 5 to configure real
  email delivery.

**Three roles**

- **Admin** — a single account (seeded automatically, see section 4) that
  oversees every class in the system. **Only admin can create a class.**
  Admin can also add/remove/reassign teachers, students, and subjects on
  **any** class, regardless of who created it.
- **Teacher panel** — teachers are *assigned* to classes and subjects (by
  admin or a class teacher) rather than creating classes themselves. Once
  assigned, a teacher can teach, take attendance for subjects they're
  assigned to, and view reports. See the permission table below for
  exactly who can do what.
- **Student panel** — enroll your face once, join a class via a join
  code, browse its subjects, see currently-open sessions, mark attendance
  in one flow, and track your attendance history and percentage
  separately for each subject.

Admin and teacher share the same dashboard/class pages — an admin account
simply has broader access and a few extra controls that appear
automatically once logged in.

**Permission model — who can do what**

| Action | Admin | Class teacher | Subject teacher | Any other teacher |
|---|---|---|---|---|
| Create a class | ✅ | ❌ | ❌ | ❌ |
| Add/remove students | ✅ | ✅ | ❌ | ❌ |
| Add/remove subjects | ✅ | ✅ | ❌ | ❌ |
| Add/remove teachers on the class | ✅ | ✅ | ❌ | ❌ |
| Designate/change who the class teacher is | ✅ | ❌ | ❌ | ❌ |
| Assign a teacher to a specific subject | ✅ | ✅ | ❌ | ❌ |
| Start / end an attendance session for a subject | ✅ | only if also that subject's teacher | ✅ | ❌ |
| View subjects, sessions, reports for the class | ✅ | ✅ | ✅ | ✅ (if assigned to the class) |
| Remove the admin from a class | ❌ (n/a) | ❌ — blocked | ❌ | ❌ |

Two roles worth explaining:

- **Class teacher** — one teacher per class, designated (and reassigned)
  by **admin only**, from the class page's Teachers tab. Once set, they
  get admin-equivalent control *over that one class*: managing its
  roster, subjects, and teacher list. They do **not** gain the ability to
  change who the class teacher is (only admin can), and they do **not**
  automatically gain the ability to start attendance sessions for every
  subject in the class — only for subjects they're also specifically
  assigned to teach (see below).
- **Subject teacher** — a teacher assigned to one specific subject (from
  the subject page's Teachers tab, by admin/class teacher). This is the
  *only* non-admin role that can start or end an attendance session for
  that subject. A class teacher who isn't also a subject's teacher cannot
  start a session for it, even though they manage everything else about
  the class. Note: admin is deliberately **never** auto-assigned as a
  subject's teacher (even when admin creates the subject) — a subject's
  teacher list stays empty until a real teacher is assigned, so it's
  always clear who's actually responsible for taking attendance.

As a safeguard, **the admin can never be removed from a class** by
anyone — that's blocked server-side regardless of who's asking.

**Class → Subject structure**

A **Class** (e.g. "BTech Data Science — Section A") is the container for
the student roster and one or more teachers. Inside it, admin/class
teacher adds any number of **Subjects** (e.g. "Data Ethics", "Machine
Learning") — each subject has its own assigned teacher(s), attendance
sessions, and attendance report, since different subjects meet at
different times and need separate tracking.

**Attendance reporting**

- **Students** see their own attendance two ways on each class page: an
  **overall percentage** combined across every subject in that class,
  and a **subject-wise breakdown table** showing present/total and % for
  each individual subject, with a link into full session-by-session
  history for any subject.
- **Teachers/admin** see a full **attendance matrix** on the class page's
  Overview tab: one row per student, one column per subject (with that
  student's percentage in each), and a final **Overall** column combining
  every subject — so you can spot at a glance who's struggling across
  the board versus who's only missing one subject. Exportable as CSV.

**Attendance security pipeline**

1. **Facial recognition** — On registration, the student's face is captured
   in the browser and converted into a 128-dimension descriptor by
   [face-api.js](https://github.com/justadudewhohacks/face-api.js) (a
   TensorFlow.js model). At attendance time, a fresh descriptor is compared
   against the enrolled one using Euclidean distance — a face that doesn't
   match is rejected.
2. **Session token** — Every attendance window ("session") gets a fresh,
   random, time-limited token, scoped to one subject. A token from
   yesterday's lecture (or a different subject) is useless today.
3. **Geo-fencing** — The classroom's GPS coordinates are captured when the
   teacher opens the session. A student's device must report a location
   within the configured radius (Haversine distance) or the check-in is
   rejected.

All three must pass before an `AttendanceRecord` is written — this is
enforced entirely server-side in `routes/attendance_routes.py`, so the
checks can't be bypassed from the browser. **Importantly, a failed check
here (wrong face, wrong location) never logs the student out** — it
returns a normal "verification failed" response with the specific reason,
and the student stays on the page with a clear way back to their
dashboard. Only actual authentication problems (a missing/invalid/expired
login token) ever force a logout.

**Dynamic, from-scratch classroom management**

- Admin creates a class at any time (no pre-seeded data required),
  optionally adding several subjects in the same step.
- Students can be added by admin/class teacher (by email) *or* self-join
  with a short class join code.
- A class can have multiple teachers assigned to it dynamically, with one
  designated as the class teacher, and each subject can further be
  assigned to a specific one of those teachers who alone can run its
  attendance sessions.
- Everything — classes, subjects, rosters, sessions, records — lives in a
  normal SQLite database and updates in real time through a JSON REST API.

---

## 2. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3 + Flask + Flask-SQLAlchemy |
| Database | SQLite (single file, zero setup) |
| Auth | JWT (PyJWT), password hashing via Werkzeug |
| Frontend | Plain HTML/CSS/JavaScript (no build step) |
| Facial recognition | face-api.js (TensorFlow.js), running **entirely in the browser** |
| Geofencing | Browser Geolocation API + server-side Haversine formula |

The face-api.js library and its model weight files are **bundled locally**
under `static/lib` and `static/models`, so face detection works without an
internet connection once the page has loaded (only the initial page load
and the webcam/GPS permissions need the browser).

---

## 3. Project structure

```
face_attendance_system/
├── app.py                  # Flask app factory + page routes
├── config.py                # All tunable settings (thresholds, expiry, etc.)
├── extensions.py             # Shared SQLAlchemy instance
├── models.py                  # User, ClassRoom, Subject, AttendanceSession, AttendanceRecord
├── requirements.txt
├── routes/
│   ├── auth_routes.py         # register / login / me / face-enroll
│   ├── teacher_routes.py      # classes, subjects, rosters, sessions, reports
│   ├── student_routes.py      # my classes, join-by-code, per-subject attendance
│   └── attendance_routes.py   # the core face+token+geofence verification
├── utils/
│   ├── auth.py                # JWT + role-based decorators
│   ├── face.py                # descriptor comparison (numpy)
│   └── geo.py                 # Haversine distance / geofence check
├── templates/                 # Jinja2 page shells (data loads via JS/API)
│   ├── index.html, login.html, register.html
│   ├── teacher/ (dashboard, class_detail, subject_detail, session_live)
│   └── student/ (dashboard, class_detail, subject_detail, enroll_face, mark_attendance)
├── static/
│   ├── css/style.css
│   ├── js/                    # api.js, face.js, geolocation.js, per-page scripts
│   ├── lib/face-api.min.js
│   └── models/                # face-api.js model weights (bundled, offline-ready)
└── instance/                  # attendance.db is created here on first run
```

---

## 4. Setup & run

**Requirements:** Python 3.9+

```bash
cd face_attendance_system
pip install -r requirements.txt

python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

The SQLite database (`instance/attendance.db`) is created automatically
the first time you run the app — no manual database setup needed.

**Admin account:** the first time you run the app, it automatically
creates a default admin account and prints the credentials right in your
terminal:
```
 Default admin account created:
   email:    admin@attendai.local
   password: admin123
```
Log in with these at `/login` (same login form as everyone else — the app
detects it's an admin account and sends you to `/admin/dashboard`). To use
your own credentials instead of the default, set the `ADMIN_EMAIL` and
`ADMIN_PASSWORD` environment variables *before* the first run (once the
account is created, changing these env vars won't retroactively update
it — you'd need to edit the row in the database, or delete
`instance/attendance.db` and restart to reseed it).

> **Camera/location permissions:** Browsers only allow camera and GPS
> access on `localhost` or over HTTPS. Running locally at
> `127.0.0.1:5000` satisfies this automatically. If you deploy this to a
> real server, put it behind HTTPS.

### Quick walkthrough

1. Log in as **admin** (credentials above — same `/login` form as everyone
   else). Click **"+ New class"** — give it a name/section and optionally
   add its subjects right there (e.g. "Data Ethics", "Machine Learning") —
   note the generated join code.
2. Register a **teacher** account at `/register` (in another browser /
   incognito tab). This account can't do anything on a class yet — it
   needs to be assigned.
3. Back as admin, open the class → Teachers tab → add that teacher's
   email → then use the **"Make class teacher"** dropdown to designate
   them as this class's class teacher. This gives them control over the
   class's roster, subjects, and teacher list (but not automatically over
   starting attendance sessions — see below).
4. As that class teacher, open the class → Subjects tab → add a subject
   (e.g. "Data Ethics"). You're automatically assigned as that subject's
   teacher too, which is what actually lets you start its sessions.
5. Register a **student** account (another browser/tab) — you'll be
   asked to enter a 6-digit code before the account is created. Since no
   email is configured by default, the code appears directly on the
   verification screen (dev-mode banner) and in the server's terminal.
   After verifying, you'll be sent straight to face enrollment — allow
   camera access and capture your face.
6. As the class teacher, add the student by email from the Students tab
   (or have the student self-join with the class's join code).
7. Open the subject → **"Start attendance session"**. Allow location
   access — this captures the classroom's location. A large token appears
   on screen with a countdown.
8. As the student, go to **"Mark attendance"**, type in the token, and
   let it scan your face + location. If everything matches, attendance is
   recorded instantly and shows up on the live session view. If it fails
   (wrong face, wrong location), you'll see exactly why and stay logged
   in — use "Try again" or "Back to dashboard".
9. Check the **Report** tab on the subject page for that subject's
   attendance percentage per student, export it as CSV, or check the
   class's **Overview** tab for attendance combined across every subject.

---

## 5. Configuration

All tunable parameters live in `config.py`:

| Setting | Purpose | Default |
|---|---|---|
| `FACE_MATCH_THRESHOLD` | Max Euclidean distance to count as a face match | `0.50` |
| `DEFAULT_SESSION_DURATION_MINUTES` | How long a session token stays valid | `10` |
| `DEFAULT_GEOFENCE_RADIUS_METERS` | Default allowed distance from classroom | `100` |
| `JWT_EXPIRY` | How long a login session lasts | `12 hours` |
| `ADMIN_EMAIL` (env var) | Login email seeded for the default admin | `admin@attendai.local` |
| `ADMIN_PASSWORD` (env var) | Login password seeded for the default admin | `admin123` |
| `OTP_EXPIRY_MINUTES` | How long a registration/reset code stays valid | `10` |
| `OTP_MAX_ATTEMPTS` | Wrong-code attempts allowed before it's invalidated | `5` |
| `PASSWORD_MIN_LENGTH` | Minimum password length | `7` |

### Sending real emails (optional)

By default, no email account is configured — OTP codes print to the
server's terminal and show in the UI as a dev-mode banner, so
registration and password reset work immediately with zero setup.

To send real emails, set these environment variables before starting
the app:

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=youraccount@gmail.com
export SMTP_PASSWORD=your-app-password    # not your regular Gmail password
export SMTP_FROM_EMAIL=youraccount@gmail.com
```

For Gmail specifically, you'll need to generate an **App Password**
(Google Account → Security → 2-Step Verification → App passwords) —
regular account passwords won't work with SMTP.

For a real deployment, set the `SECRET_KEY` and `JWT_SECRET` environment
variables to your own random values instead of the development defaults.

> **If you do set custom `SECRET_KEY`/`JWT_SECRET` values:** make sure
> they're set the *same way every time you start the server* (e.g. in a
> `.env` file or your shell profile, not typed manually into one terminal
> session). If the app is ever started with a different secret than the
> one that signed an existing browser session's token, every request from
> that browser will fail with "Invalid authorization token" until you log
> out and back in. For local testing, it's simplest to just leave the
> defaults alone.

---

## 6b. Troubleshooting: "Invalid authorization token" / unexpected logouts

If you're logged out unexpectedly or see `reason=session_expired` in the
URL:

- This is the app **detecting** a bad session and cleaning it up — not a
  crash. It happens if a token in your browser no longer matches what the
  server expects (e.g. the server was restarted with a different
  `JWT_SECRET`, or the browser is holding a token issued by a previous
  version of the app you were testing).
- The fix is always the same: just log in again — the bad token has
  already been cleared automatically.
- **Do not run the dev server with Flask's auto-reloader** (see the note
  in `app.py`'s `__main__` block) — it can restart the process mid-session
  because this app writes to `instance/attendance.db` on nearly every
  request, and the reloader can mistake that for a code change. The
  shipped default already disables it.
- If it keeps happening on a *freshly issued* token (i.e. it fails
  immediately after a successful login), check your terminal — the server
  now prints a line like `[auth] 401 on /api/... : <reason>` explaining
  exactly why the token was rejected.

---

## 6. Notes on the facial recognition approach

Rather than running a heavyweight native computer-vision stack (e.g.
`dlib`/`face_recognition`, which needs a C++ toolchain to compile) on the
server, this project uses **face-api.js in the browser** to do face
detection, landmark alignment, and descriptor extraction. The server only
ever receives a 128-number descriptor — never a raw photo — and does a
lightweight Euclidean-distance comparison with `numpy`. This keeps the
Python backend dependency-light and portable while still using a real
pretrained deep-learning face recognition model.

---

## 7. Known limitations / ideas to extend

- The face descriptor is stored as a single reference vector per student;
  capturing 2–3 samples and averaging them would improve robustness to
  lighting changes.
- There's no password-reset flow — add one before using this beyond a
  class project. This also means the admin password can't be changed
  from inside the app yet; set `ADMIN_PASSWORD` before first run, or edit
  the database directly.
- `AttendanceSession` currently supports one active session per class at
  a time by convention (the UI doesn't prevent starting a second one);
  add a uniqueness check if you need to enforce that strictly.
- For production use, swap Flask's built-in dev server for a proper WSGI
  server (e.g. gunicorn) and put the app behind HTTPS.
