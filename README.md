## Spark PR Review Board

This repository hosts the code for [spark-prs.appspot.com](spark-prs.appspot.com), a tool for assisting in [Apache Spark](https://github.com/apache/spark/) pull request review.

## Development Instructions

1. Install the [App Engine Python SDK](https://developers.google.com/appengine/downloads).
2. Install dependencies:

   ```
   pip install -r requirements.txt -t lib
   ```
3. Create a `settings.cfg` file (see `settings.cfg.template`)
3. Run `dev_appserver.py .` and browse to [http://localhost:8080](http://localhost:8080) to view the application.

