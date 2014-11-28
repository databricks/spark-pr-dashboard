## Spark PR Review Board

[![Build Status](https://travis-ci.org/databricks/spark-pr-dashboard.svg?branch=master)](https://travis-ci.org/databricks/spark-pr-dashboard)

This repository hosts the code for [spark-prs.appspot.com](http://spark-prs.appspot.com), a tool for assisting in [Apache Spark](https://github.com/apache/spark/) pull request review.

## Development Instructions

1. Install the [App Engine Python SDK](https://developers.google.com/appengine/downloads).
2. Install dependencies:

   ```
   pip install -r requirements.txt -t lib
   npm install .
   ```
3. Run `git submodule init` and `git submodule update` to fetch Git submodules.
4. Create a `settings.cfg` file (see `settings.cfg.template`)
5. Run `dev_appserver.py .` and browse to [http://localhost:8080](http://localhost:8080) to view the application.

Initially, the dashboard will be empty because the dev appserver doesn't run the cron job that updates issues. To trigger the job manually, browse to [http://localhost:8000/cron](http://localhost:8000/cron) and hit "Run now".

## License

This project is licensed under the Apache 2.0 License. See LICENSE for full license text.
