define([
    'react',
    'jquery',
    'underscore',
    'views/TableView'
  ],
  function(React, $, _, TableView) {
    'use strict';

    var UsersTableRow = React.createClass({displayName: "UsersTableRow",
      render: function() {
        var href = '/users/' + this.props.username;
        return (
          React.createElement("tr", null, 
            React.createElement("td", null, React.createElement("a", {href: href}, this.props.username)), 
            React.createElement("td", null, this.props.numOpenPrs)
          )
        );
      }
    });

    var UsersPage = React.createClass({displayName: "UsersPage",

      columnNames: ['Username', 'Open PRs'],

      sortFunctions: {
        'Username': function(row) { return row.props.username.toLowerCase(); },
        'Open PRs': function(row) { return row.props.numOpenPrs; }
      },

      tableRows: function() {
        var prsByUser = _.groupBy(this.props.prs, function(pr) { return pr.user; });
        var tableRows = _.map(prsByUser, function(prs, username) {
          return (React.createElement(UsersTableRow, {key: username, username: username, numOpenPrs: prs.length}));
        });
        return tableRows;
      },

      render: function() {
        return (
          React.createElement("div", {className: "container"}, 
            React.createElement("h3", null, "All Users"), 
            React.createElement(TableView, {
              rows: this.tableRows(), 
              columnNames: this.columnNames, 
              sortFunctions: this.sortFunctions, 
              initialSortCol: "Open PRs", 
              initialSortDirection: "desc"})
          )
          );
      }
    });

    return UsersPage;
  }
);
