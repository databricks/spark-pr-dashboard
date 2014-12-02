## Spark PR Review Board

[![Build Status](https://travis-ci.org/databricks/spark-pr-dashboard.svg?branch=master)](https://travis-ci.org/databricks/spark-pr-dashboard)

This repository hosts the code for [spark-prs.appspot.com](http://spark-prs.appspot.com), a tool for assisting in [Apache Spark](https://github.com/apache/spark/) pull request review.

The backend is written in Python and hosted via Google App Engine.  It uses a periodic cron job to access the GitHub API, fetch lists of recently-updated pull requests, and enqueue tasks to download PR information and persist it into a database.  The backend has several other functions, including:

- Classification of pull requests based on which files they modify.
- Automatically linking JIRA issues to pull requests that reference them.
- Triggering Jenkins jobs to test pull requests (experimental / admin-only).

The frontend uses [React.js](https://facebook.github.io/react/) to render UI components.  It communicates with the backend via a REST API.

## Development Instructions

1. Install the [App Engine Python SDK](https://developers.google.com/appengine/downloads).
2. Install dependencies:

   ```
   pip install -r requirements.txt -t lib
   npm install .
   ```
3. Create a `settings.cfg` file (see `settings.cfg.template`)
4. Run `dev_appserver.py .` and browse to [http://localhost:8080](http://localhost:8080) to view the application.

Initially, the dashboard will be empty because the dev appserver doesn't run the cron job that updates issues. To trigger the job manually, browse to [http://localhost:8000/cron](http://localhost:8000/cron) and hit "Run now".

## Code Style

For Python code, we follow the [PEP8](https://www.python.org/dev/peps/pep-0008) style, with the exception of a 100-character maximum line length instead 80.

For Javascript code, we roughly follow the [Airbnb stlye guide](https://github.com/airbnb/javascript).

To perform style checks:

```
pep8
grunt lint
```

## License

This project is licensed under the Apache 2.0 License. See LICENSE for full license text.
