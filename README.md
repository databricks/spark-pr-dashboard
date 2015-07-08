## Spark PR Review Board

[![Build Status](https://travis-ci.org/databricks/spark-pr-dashboard.svg?branch=master)](https://travis-ci.org/databricks/spark-pr-dashboard)
[![devDependency
Status](https://david-dm.org/databricks/spark-pr-dashboard/dev-status.svg)](https://david-dm.org/databricks/spark-pr-dashboard#info=devDependencies)

This repository hosts the code for [spark-prs.appspot.com](http://spark-prs.appspot.com), a tool for assisting in [Apache Spark](https://github.com/apache/spark/) pull request review.

The backend is written in Python and hosted via Google App Engine.  It uses a periodic cron job to access the GitHub API, fetch lists of recently-updated pull requests, and enqueue tasks to download PR information and persist it into a database.  The backend has several other functions, including:

- Classification of pull requests based on which files they modify.
- Automatically linking JIRA issues to pull requests that reference them.
- Triggering Jenkins jobs to test pull requests (experimental / admin-only).

The frontend uses [React.js](https://facebook.github.io/react/) to render UI components.  It communicates with the backend via a REST API.

## Development Instructions

### Installing dependencies
1. Install the [App Engine Python SDK](https://developers.google.com/appengine/downloads).
2. Install library dependencies:

   ```
   pip install -r requirements.txt -t lib
   npm install .   
   ```
3. Create a `settings.cfg` file (see `settings.cfg.template`).  For most user-facing feature development, it is not necessary to fill out the entire `settings.cfg` file.  However, you may need to supply several of these configuration options in order to test certain backend functionality, such as GitHub data-fetching and authentication, JIRA integration, etc.
4. Run `dev_appserver.py --datastore_path datastore .` and browse to [http://localhost:8080](http://localhost:8080) to view the application.

###  Loading Data
Initially, the dashboard will be empty because the development appserver doesn't run the cron job that contacts GitHub to download pull requests.  The easiest way to get started is to [download a sample database dump](https://www.dropbox.com/s/uoxgx3c028r1pj9/datastore?dl=0) and pass the `--datastore_path /path/to/downloaded/datastore` option to `dev_appserver.py`.

If you'd rather generate your own datastore, configure `settings.cfg` with proper GitHub API keys, then browse to [http://localhost:8000/cron](http://localhost:8000/cron) and hit "Run now" to manually trigger the cron job that refreshes pull requests.

### Front-end development

The front-end UI is implemented as a single-page web app using the [React.js](https://facebook.github.io/react/) library.  The majority of UI components are written in React's [JSX](https://facebook.github.io/react/docs/jsx-in-depth.html) Javascript dialect; these files have `.jsx` extensions.  These JSX files are converted into plain Javascript using a [Grunt](http://gruntjs.com/) task.

A good development workflow is to run `grunt default watch` in a separate terminal so that Grunt watches files for changes and automatically performs the JS -> JSX conversion and runs the code style checks.

For now, we commit both the `.jsx` source files and generated `.js` files.  In the longer run, it would be a good idea to use something like Browserify or Uglify.js to compile our Javascript source files into a single file and to not check in generated sources (pull requests are welcome for this!).

## Code Style

For Python code, we follow the [PEP8](https://www.python.org/dev/peps/pep-0008) style, with the exception of a 100-character maximum line length instead 80.

For Javascript code, we roughly follow the [Airbnb style guide](https://github.com/airbnb/javascript).

To perform style checks:

```
pep8
grunt lint
```

## License

This project is licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for full license text.
