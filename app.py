import os
from dotenv import load_dotenv
from app import create_app, db
from app.models import Account, Email

# Load environment variables
load_dotenv()

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'Account': Account, 'Email': Email}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
