define([
    'react',
    'react-mini-router',
    'jquery',
    'underscore',
    'views/Dashboard',
    'views/UsersPage',
    'views/UserDashboard',
    'views/reports/OpenJIRAsWithClosedPRsReport'
  ],
  function(React, Router, $, _, Dashboard, UsersPage, UserDashboard, OpenJIRAsWithClosedPRsReport) {
    "use strict";

    var RouterMixin = Router.RouterMixin;

    var NavigationHeader = React.createClass({displayName: 'NavigationHeader',
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

    var GitHubUser = React.createClass({displayName: 'GitHubUser',
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

    var GitHubLogin = React.createClass({displayName: 'GitHubLogin',
      render: function() {
        return (
          React.createElement("a", {href: "/login", className: "btn btn-default navbar-btn"}, 
            React.createElement("span", {className: "octicon octicon-sign-in"}), " Sign in"
          )
        );
      }
    });

    var GitHubLogout = React.createClass({displayName: 'GitHubLogout',
      render: function() {
        return (
          React.createElement("a", {href: "/logout", className: "btn btn-default navbar-btn"}, 
            React.createElement("span", {className: "octicon octicon-sign-out"}), " Sign out"
          )
        );
      }
    });

    var GitHub = React.createClass({displayName: 'GitHub',
      render: function() {
        var githubUser, githubAction;
        if (this.props.user !== null) {
          githubUser = React.createElement(GitHubUser, {username: this.props.user.github_login});
          githubAction = React.createElement(GitHubLogout, null);
        } else {
          githubAction = React.createElement(GitHubLogin, null);
        }

        return (
          React.createElement("div", {className: "pull-right"}, 
            githubUser, 
            React.createElement("a", {href: "https://github.com/databricks/spark-pr-dashboard", 
              className: "btn btn-success navbar-btn"}, 
              React.createElement("span", {className: "octicon octicon-mark-github"}), 
            "Fork me on GitHub"
            ), 
            githubAction
          )
        );
      }
    });

    var AppManager = React.createClass({displayName: 'AppManager',
      mixins: [RouterMixin],

      routes: {
        '/': 'openPrs',
        '/open-prs': 'openPrs',
        '/users/': 'users',
        '/users/:username*': 'userDashboard',
        '/reports/open-jira-issues-with-closed-prs': 'openJIRAsWithClosedPRsReport'
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

      openJIRAsWithClosedPRsReport: function() {
        return (React.createElement(OpenJIRAsWithClosedPRsReport, null));
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

        var reportsTab = (
          React.createElement("li", {className: pathname.indexOf('/reports') === 0 ? "dropdown active" : "dropdown"}, 
            React.createElement("a", {
              href: "#", 
              className: "dropdown-toggle", 
              'data-toggle': "dropdown", 
              role: "button", 
              'aria-expanded': "false"}, "Reports", React.createElement("span", {className: "caret"})), 
            React.createElement("ul", {className: "dropdown-menu", role: "menu"}, 
              React.createElement("li", null, React.createElement("a", {href: "/reports/open-jira-issues-with-closed-prs"}, 
                "Open JIRA issues with closed PRs"
              ))
            )
          )
        );

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
                  reportsTab, 
                  this.userIsAdmin() ? adminTab : ""
                ), 

                React.createElement(GitHub, {user: this.state.user})
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
