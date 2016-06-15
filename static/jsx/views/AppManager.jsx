define([
    'react',
    'react-mini-router',
    'jquery',
    'underscore',
    'views/Dashboard',
    'views/StaleDashboard',
    'views/UsersPage',
    'views/UserDashboard'
  ],
  function(React, Router, $, _, Dashboard, StaleDashboard, UsersPage, UserDashboard) {
    "use strict";

    var RouterMixin = Router.RouterMixin;

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
            <span className="signed-in-as-text">Signed in as</span>
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

    var RefreshButton = React.createClass({
      render: function() {
        return (
          <a className="btn btn-default navbar-btn"
             onClick={this.props.onClick}
             disabled={!this.props.enabled}>
            <span className="octicon octicon-sync"></span>
            Refresh
          </a>
        );
      }
    });

    var AppManager = React.createClass({
      mixins: [RouterMixin],

      routes: {
        '/': 'openPrs',
        '/open-prs': 'openPrs',
        '/stale-prs': 'staleOpenPrs',
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
          <Dashboard
            prs={this.state.prs}
            showJenkinsButtons={this.userCanUseJenkins()}/>
          );
      },

      staleOpenPrs: function() {
        return (
          <StaleDashboard
            prs={this.state.stalePrs}
            showJenkinsButtons={this.userCanUseJenkins()}/>
          );
      },

      users: function() {
        return (<UsersPage prs={this.state.prs}/>);
      },

      userDashboard: function(username) {
        return (
          <UserDashboard
            prs={this.state.prs}
            username={username}
            showJenkinsButtons={this.userCanUseJenkins()}/>);
      },

      getInitialState: function() {
        return {prs: [], stalePrs: [], user: null, refreshInProgress: false};
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
        this.refreshStalePrs();
      },

      refreshStalePrs: function() {
        var _this = this;
        this.setState({refreshInProgress: true});
        console.log("Refreshing stale pull requests");
        $.ajax({
          url: '/search-stale-prs',
          dataType: 'json',
          success: function(stalePrs) {
            _this.setState({stalePrs: stalePrs, refreshInProgress: false});
            console.log("Done refreshing stale pull requests; stalePrs.length=" + stalePrs.length);
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
          <span className="badge">
            {this.state.prs.length}
          </span>
        );

        var countStalePrsBadge = (
          <span className="badge">
            {this.state.stalePrs.length}
          </span>
        );

        var adminTab = (
          <li className={pathname === '/admin' ? "active" : ""}>
            <a href="/admin">
            Admin
            </a>
          </li>
        );

        var githubUser;
        if (this.state.user !== null) {
          console.log(this.state.user);
          githubUser = (<GitHubUser username={this.state.user.github_login}/>);
        }

        var loginButton;
        if (this.state.user !== null) {
          loginButton = <GitHubLogout/>;
        } else {
          loginButton = <GitHubLogin/>;
        }

        return (
          <div>
            <nav id="main-nav" className="navbar navbar-default"
              role="navigation">
              <div className="container-fluid">
                <NavigationHeader/>

                <ul className="nav navbar-nav">
                  <li className={(pathname === '/open-prs' || pathname === '/') ? "active" : ""}>
                    <a href="/open-prs">
                      Open PRs {countPrsBadge}
                    </a>
                  </li>
                  <li className={(pathname === '/stale-prs') ? "active" : ""}>
                    <a href="/stale-prs">
                      Stale PRs {countStalePrsBadge}
                    </a>
                  </li>
                  <li className={pathname.indexOf('/users') === 0 ? "active" : ""}>
                    <a href="/users">
                    Users
                    </a>
                  </li>
                  {this.userIsAdmin() ? adminTab : ""}
                </ul>
                <div className="pull-right">
                  {githubUser}
                  <RefreshButton onClick={this.refreshPrs} enabled={!this.state.refreshInProgress}/>
                  {loginButton}
                </div>
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
