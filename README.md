========================================================================
ELEGANCE FUR REAL PET SALON CRM HUB - SETUP & USER GUIDE
========================================================================

A lightweight web-based CRM system built using Python 3, Flask, and SQLite.

------------------------------------------------------------------------
1. HOW TO RUN THE SYSTEM
------------------------------------------------------------------------

Step 1: Open Terminal / Command Prompt in the Project Folder
  - Open File Explorer and open the folder containing "app.py".
  - Click on the address bar at the top, type "cmd", and press Enter.

Step 2: Install Flask
  - In the Command Prompt window, type:
      py -m pip install flask
  - Press Enter and wait for the installation to finish.

Step 3: Run the Application
  - Type:
      python app.py
  - Press Enter.
  - You will see: "* Running on http://127.0.0.1:5000"
  - Keep this black terminal window open while using the website.

Step 4: Open in Web Browser
  - Open Google Chrome, Microsoft Edge, or any browser.
  - Go to the address:
      http://127.0.0.1:5000


------------------------------------------------------------------------
2. HOW TO STOP AND RESET THE SYSTEM
------------------------------------------------------------------------

To Stop the Server:
  - Go to the terminal window where the app is running.
  - Press: Ctrl + C

To Reset Database to Default Seed Data:
  - Make sure the app is stopped first (Ctrl + C).
  - In the terminal, type:
      python seed.py --reset
  - Press Enter. This restores the original clean seed records.
  - Then run "python app.py" again to start fresh.


------------------------------------------------------------------------
3. DEMO LOGIN ACCOUNTS
------------------------------------------------------------------------

You can log in using either the email or username:

1. ADMIN (Owner / Manager)
   - Email / Username: admin@demo.com  (or: admin)
   - Password:         Admin123!
   - Access:           Full system access, staff accounts, CLV rules,
                       and business reports.

2. RECEPTIONIST (Front Desk)
   - Email / Username: joanna.receptionist@demo.com  (or: joanna.receptionist)
   - Password:         Receptionist123!
   - Access:           Book appointments, add customers/pets, manage sales
                       leads, and open support tickets.

3. GROOMER (Staff)
   - Email / Username: marco.groomer@demo.com  (or: marco.groomer)
   - Password:         Groomer123!
   - Access:           Daily grooming schedule, view pet allergy warnings,
                       and mark jobs as Completed.


------------------------------------------------------------------------
4. QUICK TESTING WORKFLOW
------------------------------------------------------------------------

1. Test Appointment Booking:
   - Sign in as Receptionist (joanna.receptionist@demo.com / Receptionist123!).
   - Click "+ New appointment".
   - Pick a customer, pet, groomer, date, time, and service.
   - Click "Book appointment".

2. Test Scheduling Collision Prevention:
   - Attempt to book another appointment for the same groomer at the
     same time slot.
   - The system will block it with a conflict error message.

3. Test Automated CLV & Tier Updates:
   - Sign in as Groomer (marco.groomer@demo.com / Groomer123!).
   - In Appointments, click "Start" then "Complete" on an assigned job.
   - Sign in as Receptionist or Admin, open "Segments & CLV", and see
     the customer's spending and segment automatically update.
========================================================================
