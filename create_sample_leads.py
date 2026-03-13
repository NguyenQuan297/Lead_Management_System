"""Create a sample leads.xlsx file for testing upload."""
import pandas as pd
from datetime import datetime, timedelta

rows = [
    ("Nguyen Van A", "0988888888", datetime.now() - timedelta(hours=20)),
    ("Tran Thi B", "0977777777", datetime.now() - timedelta(hours=2)),
    ("Le Van C", "0966666666", datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)),
]
df = pd.DataFrame(rows, columns=["name", "phone", "created_date"])
df.to_excel("sample_leads.xlsx", index=False)
print("Created sample_leads.xlsx")
