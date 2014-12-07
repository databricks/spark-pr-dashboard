define([
    'react',
    'react-mini-router',
    'jquery',
    'underscore',
    'views/Dashboard',
    'views/UserDashboard'
  ],
  function(React, Router, $, _, Dashboard, UserDashboard) {
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
        '/users/:username*': 'users'
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

      users: function(username) {
        return (
          React.createElement(UserDashboard, {
            prs: this.state.prs, 
            username: username, 
            showJenkinsButtons: this.userCanUseJenkins()}));
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
        var countPrsBadge = (
          React.createElement("span", {className: "badge"}, 
            this.state.prs.length
          )
        );

        var adminTab = (
          React.createElement("li", null, 
            React.createElement("a", {href: "/admin"}, 
            "Admin"
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
                  React.createElement("li", {className: "active"}, 
                    React.createElement("a", {href: "/open-prs"}, 
                      "Open PRs by Component ", countPrsBadge
                    )
                  ), 
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
