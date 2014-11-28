// jscs:disable
define([
    'react',
    'react-mini-router',
    'jquery',
    'views/Dashboard',
    'views/UserDashboard'
  ],
  function(React, Router, $, Dashboard, UserDashboard) {
    "use strict";

    var RouterMixin = Router.RouterMixin;
    var navigate = Router.navigate;

    // jscs:enable
    var NavigationHeader = React.createClass({
      render: function() {
        return (
          <div className="navbar-header">
            <a className="navbar-brand" href="/">
              Spark Pull Requests
            </a>
          </div>
        );
      }
    });

    var GitHubUser = React.createClass({
      render: function() {
        var link = "/users/" + this.props.username;
        return (
          <p className="nav navbar-text">
          Signed in as
            <a href={link} className="navbar-link">{this.props.username}</a>
          </p>
        );
      }
    });

    var GitHubLogin = React.createClass({
      render: function() {
        return (
          <a href="/login" className="btn btn-default navbar-btn">
            <span className="octicon octicon-sign-in"></span> Sign in
          </a>
        );
      }
    });

    var GitHubLogout = React.createClass({
      render: function() {
        return (
          <a href="/logout" className="btn btn-default navbar-btn">
            <span className="octicon octicon-sign-out"></span> Sign out
          </a>
        );
      }
    });

    var GitHub = React.createClass({
      render: function() {
        var githubUser, githubAction;
        if (this.props.user !== null) {
          githubUser = <GitHubUser username={this.props.user.github_login}/>;
          githubAction = <GitHubLogout/>;
        } else {
          githubAction = <GitHubLogin/>;
        }

        return (
          <div className="pull-right">
            {githubUser}
            <a href="https://github.com/databricks/spark-pr-dashboard"
              className="btn btn-success navbar-btn">
              <span className="octicon octicon-mark-github"></span>
            Fork me on GitHub
            </a>
            {githubAction}
          </div>
        );
      }
    });

    var AppManager = React.createClass({
      mixins: [RouterMixin],

      routes: {
        '/': 'openPrs',
        '/open-prs': 'openPrs',
        '/users/:username*': 'users'
      },

      openPrs: function() {
        return <Dashboard prs={this.state.prs}/>;
      },

      users: function(username) {
        return <UserDashboard prs={this.state.prs} username={username}/>;
      },

      getInitialState: function() {
        return {prs: [], user: null};
      },

      componentDidMount: function() {
        var _this = this;

        $.ajax({
          url: '/search-open-prs',
          dataType: 'json',
          success: function(prs) {
            _this.setState({prs: prs});
          }
        });
      },

      render: function() {
        var countPrsBadge = (
          <span className="badge">
            {this.state.prs.length}
          </span>
        );

        return (
          <div>
            <nav id="main-nav" className="navbar navbar-default"
              role="navigation">
              <div className="container-fluid">
                <NavigationHeader/>

                <ul className="nav navbar-nav">
                  <li className="active">
                    <a href="/open-prs">
                      Open PRs by Component {countPrsBadge}
                    </a>
                  </li>
                </ul>

                <GitHub user={this.state.user}/>
              </div>
            </nav>

            {this.renderCurrentRoute()}
          </div>
        );
      }
    });

    return AppManager;
  }
);
