define([
    'react',
    'jquery',
    'underscore',
    'views/TableView',
    'mixins/UrlMixin'
  ],
  function(React, $, _, TableView, UrlMixin) {
    'use strict';

    var UsersTableRow = React.createClass({displayName: "UsersTableRow",
      render: function() {
        var href = '/users/' + this.props.username;
        return (
          React.createElement("tr", null, 
            React.createElement("td", null, this.props.rank), 
            React.createElement("td", null, React.createElement("a", {href: href}, this.props.username)), 
            React.createElement("td", null, this.props.authored), 
            React.createElement("td", null, this.props.reviewed)
          )
        );
      }
    });

    var NavItem = React.createClass({displayName: "NavItem",
      mixins: [UrlMixin],
      onClick: function(event) {
        var component = this.props.component;
        var hash = window.location.hash.split(/#|&/);
        if (hash.length === 3) {
          this.pushAnchor(component, hash[1]);
        } else {
          this.pushAnchor(component);
        }
      },

      render: function() {
        return (
          React.createElement("li", {className: this.props.active ? "subnav-active" : ""}, 
            React.createElement("a", {onClick: this.onClick}, 
              this.props.component
            )
          )
        );
      }
    });

    var ContributorsPage = React.createClass({displayName: "ContributorsPage",
      mixins: [UrlMixin],
      getInitialState: function() {
        return {activeTab: ''};
      },

      columnNames: ['', 'Username', 'PRs Authored', 'PRs Reviewed'],

      sortFunctions: {
        '': function(row) { return row.props.rank; },
        'Username': function(row) { return row.props.username.toLowerCase(); },
        'PRs Authored': function(row) { return row.props.authored; },
        'PRs Reviewed': function(row) { return row.props.reviewed; }
      },

      tableRows: function(component) {
        var topContributors = this.props.topContributors;
        var users = [];
        if (topContributors) {
          users = topContributors[component];
        }
        var tableRows = _.map(users, function(user, index) {
          return (
            React.createElement(UsersTableRow, {
              rank: index + 1, 
              username: user[0], 
              authored: user[1][0], 
              reviewed: user[1][1]}));
        });
        return tableRows;
      },

      componentDidMount: function() {
        if (this.props.topContributors) {
          this._prepareData(this.props.topContributors);
        }
      },

      componentWillReceiveProps: function(nextProps) {
        this._prepareData(nextProps.topContributors);
      },

      componentDidUpdate: function(prevProps, prevState) {
        var newActiveTab = this.state.activeTab;
        if (prevState.activeTab !== newActiveTab) {
          this.setState({ activeTab: newActiveTab });
        }
      },

      _prepareData: function(topContributors) {
        var tab = this._checkTabAvailability(topContributors);

        this.setState({ activeTab: tab ? tab : "Core" });
      },

      _checkTabAvailability: function(topContributors) {
        var hash = window.location.hash.split(/#|&/);
        var anchor = hash.pop();

        for (var component in topContributors) {
          if (this.getAnchor(component) === anchor) {
            return component;
          }
        }
      },

      render: function() {
        var navItems = [], userTables = [];
        var display_none = { display: 'none' };
        var display_block = { display: 'block' };

        var activeTab = this.state.activeTab;
        var topContributors = this.props.topContributors;

        for (var component in topContributors) {
          navItems.push(
            React.createElement(NavItem, {
              component: component, 
              active: component === activeTab})
          );
          userTables.push(
            React.createElement("div", {id: component, style: component === activeTab ? display_block : display_none}, 
              React.createElement(TableView, {
                rows: this.tableRows(component), 
                columnNames: this.columnNames, 
                sortFunctions: this.sortFunctions})
            )
          );
        }

        var navBar = (
          React.createElement("nav", {className: "sub-nav navbar navbar-default", role: "navigation"}, 
            React.createElement("div", {className: "container-fluid"}, 
              React.createElement("ul", {className: "nav navbar-nav"}, 
                navItems
              )
            )
          )
        );


        return (
          React.createElement("div", null, 
            navBar, 
            React.createElement("div", {className: "container"}, 
              userTables
            )
          )
          );
      }
    });

    return ContributorsPage;
  }
);
