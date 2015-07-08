define([
    'react',
    'react-mini-router',
    'jquery',
    'underscore',
    'views/Dashboard',
    'views/UsersPage',
    'views/UserDashboard'
  ],
  function(React, Router, $, _, Dashboard, UsersPage, UserDashboard) {
    "use strict";

    var RouterMixin = Router.RouterMixin;

    var NavigationHeader = React.createClass({displayName: "NavigationHeader",
      render: function() {
        return (
          React.createElement("div", {className: "navbar-header"}, 
            React.createElement("a", {className: "navbar-brand", href: "/"}, 
              "Spark Pull Requests"
            )
          )
        );
      }
    });

    var GitHubUser = React.createClass({displayName: "GitHubUser",
      render: function() {
        var link = "/users/" + this.props.username;
        return (
          React.createElement("p", {className: "nav navbar-text"}, 
            React.createElement("span", {className: "signed-in-as-text"}, "Signed in as"), 
            React.createElement("a", {href: link, className: "navbar-link"}, this.props.username)
          )
        );
      }
    });

    var GitHubLogin = React.createClass({displayName: "GitHubLogin",
      render: function() {
        return (
          React.createElement("a", {href: "/login", className: "btn btn-default navbar-btn"}, 
            React.createElement("span", {className: "octicon octicon-sign-in"}), " Sign in"
          )
        );
      }
    });

    var GitHubLogout = React.createClass({displayName: "GitHubLogout",
      render: function() {
        return (
          React.createElement("a", {href: "/logout", className: "btn btn-default navbar-btn"}, 
            React.createElement("span", {className: "octicon octicon-sign-out"}), " Sign out"
          )
        );
      }
    });

    var RefreshButton = React.createClass({displayName: "RefreshButton",
      render: function() {
        return (
          React.createElement("a", {className: "btn btn-default navbar-btn", 
             onClick: this.props.onClick, 
             disabled: !this.props.enabled}, 
            React.createElement("span", {className: "octicon octicon-sync"}), 
            "Refresh"
          )
        );
      }
    });

    var AppManager = React.createClass({displayName: "AppManager",
      mixins: [RouterMixin],

      routes: {
        '/': 'openPrs',
        '/open-prs': 'openPrs',
        '/users/': 'users',
        '/users/:username*': 'userDashboard'
      },

      userIsAdmin: function() {
        return this.state.user && _.contains(this.state.user.roles, "admin");
      },

      userCanUseJenkins: function() {
        return this.state.user && _.contains(this.state.user.roles, "jenkins-admin");
      },

      openPrs: function() {
        return (
          React.createElement(Dashboard, {
            prs: this.state.prs, 
            showJenkinsButtons: this.userCanUseJenkins()})
          );
      },

      users: function() {
        return (React.createElement(UsersPage, {prs: this.state.prs}));
      },

      userDashboard: function(username) {
        return (
          React.createElement(UserDashboard, {
            prs: this.state.prs, 
            username: username, 
            showJenkinsButtons: this.userCanUseJenkins()}));
      },

      getInitialState: function() {
        return {prs: [], user: null, refreshInProgress: false};
      },

      refreshPrs: function() {
        var _this = this;
        this.setState({refreshInProgress: true});
        console.log("Refreshing pull requests");
        $.ajax({
          url: '/search-open-prs',
          dataType: 'json',
          success: function(prs) {
            _this.setState({prs: prs, refreshInProgress: false});
            console.log("Done refreshing pull requests; prs.length=" + prs.length);
          },
          error: function() {
            _this.setState({refreshInProgress: false});
          }
        });
      },

      refreshUserInfo: function() {
        var _this = this;
        $.ajax({
          url: '/user-info',
          dataType: 'json',
          success: function(user) {
            if (user) {
              _this.setState({user: user});
            }
          }
        });
      },

      componentDidMount: function() {
        this.refreshPrs();
        this.refreshUserInfo();
        // Refresh every 5 minutes:
        this.refreshInterval = window.setInterval(this.refreshPrs, 1000 * 60 * 5);
      },

      componentWillUnmount: function() {
        window.clearInterval(this.refreshInterval);
      },

      render: function() {
        var pathname = window.location.pathname;

        var countPrsBadge = (
          React.createElement("span", {className: "badge"}, 
            this.state.prs.length
          )
        );

        var adminTab = (
          React.createElement("li", {className: pathname === '/admin' ? "active" : ""}, 
            React.createElement("a", {href: "/admin"}, 
            "Admin"
            )
          )
        );

        var githubUser;
        if (this.state.user !== null) {
          console.log(this.state.user);
          githubUser = (React.createElement(GitHubUser, {username: this.state.user.github_login}));
        }

        var loginButton;
        if (this.state.user !== null) {
          loginButton = React.createElement(GitHubLogout, null);
        } else {
          loginButton = React.createElement(GitHubLogin, null);
        }

        return (
          React.createElement("div", null, 
            React.createElement("nav", {id: "main-nav", className: "navbar navbar-default", 
              role: "navigation"}, 
              React.createElement("div", {className: "container-fluid"}, 
                React.createElement(NavigationHeader, null), 

                React.createElement("ul", {className: "nav navbar-nav"}, 
                  React.createElement("li", {className: (pathname === '/open-prs' || pathname === '/') ? "active" : ""}, 
                    React.createElement("a", {href: "/open-prs"}, 
                      "Open PRs ", countPrsBadge
                    )
                  ), 
                  React.createElement("li", {className: pathname.indexOf('/users') === 0 ? "active" : ""}, 
                    React.createElement("a", {href: "/users"}, 
                    "Users"
                    )
                  ), 
                  this.userIsAdmin() ? adminTab : ""
                ), 
                React.createElement("div", {className: "pull-right"}, 
                  githubUser, 
                  React.createElement(RefreshButton, {onClick: this.refreshPrs, enabled: !this.state.refreshInProgress}), 
                  React.createElement("a", {href: "https://github.com/databricks/spark-pr-dashboard", 
                     className: "btn btn-default navbar-btn"}, 
                    React.createElement("span", {className: "octicon octicon-mark-github"}), 
                      "Fork me on GitHub"
                  ), 
                  loginButton
                )
              )
            ), 

            this.renderCurrentRoute()
          )
        );
      }
    });

    return AppManager;
  }
);
