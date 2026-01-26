# Roommate Schedule Optimizer

Finds the best schedule combinations for two roommates to maximize their overlapping time in the dorm.

## How it works

1. Each roommate enters their **fixed events** (classes, work — set times) and **flexible events** (gym, studying — just need a duration)
2. The algorithm generates all valid ways to place the flexible events
3. It cross-products both roommates' schedules and scores each pair by hours spent together in the dorm
4. Returns the top 10 combinations

## Setup

### Backend

```bash
cd your-project-folder
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd roommate-app
npm install
npm run dev
```

Open http://localhost:5174 in your browser.

## API

**POST /analyze**

Request body:
```json
{
  "roommate_a": {
    "roommate_name": "Alice",
    "fixed_events": [
      {"name": "Class", "start": 9, "finish": 11, "in_dorm": false}
    ],
    "flexible_events": [
      {"name": "Study", "duration": 2, "in_dorm": true}
    ]
  },
  "roommate_b": {
    "roommate_name": "Bob",
    "fixed_events": [],
    "flexible_events": []
  }
}
```

Returns top 10 schedule combinations with overlap scores.
