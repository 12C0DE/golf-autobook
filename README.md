┌──────────────────────────────────────────────────────────┐
│              Frontend (React + Vite + Tailwind)          │
│  - Retro Gruvbox Pixel UI Console                        │
│  - User selects Date, Course, Player Count, Time Window  │
└────────────────────────────┬─────────────────────────────┘
                             │
                             │ HTTP POST (JSON Payload)
                             ▼
┌──────────────────────────────────────────────────────────┐
│              AWS Lambda / API Gateway                    │
│  - Docker Container (Python 3.11 in ECR)                 │
│  - app.py (handler)                                      │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ├─► 1. Authenticate with MemberSports API
                             ├─► 2. Query Availability Sheet for Date
                             ├─► 3. Acquire AppSync & REST Lock Holds
                             └─► 4. Post Final Booking Payload
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│             Third-Party Booking Infrastructure           │
│  - MemberSports REST API (api.membersports.com)          │
│  - AWS AppSync GraphQL (Broadcast Lock)                  │
└──────────────────────────────────────────────────────────┘
