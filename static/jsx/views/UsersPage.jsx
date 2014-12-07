define([
    'react',
    'jquery',
    'underscore',
    'views/TableView'
  ],
  function(React, $, _, TableView) {
    'use strict';

    var UsersTableRow = React.createClass({
      render: function() {
        var href = '/users/' + this.props.username;
        return (
          <tr>
            <td><a href={href}>{this.props.username}</a></td>
            <td>{this.props.numOpenPrs}</td>
          </tr>
        );
      }
    });

    var UsersPage = React.createClass({

      columnNames: ['Username', 'Open PRs'],

      sortFunctions: {
        'Username': function(row) { return row.props.username.toLowerCase(); },
        'Open PRs': function(row) { return row.props.numOpenPrs; }
      },

      tableRows: function() {
        var prsByUser = _.groupBy(this.props.prs, function(pr) { return pr.user; });
        var tableRows = _.map(prsByUser, function(prs, username) {
          return (<UsersTableRow key={username} username={username} numOpenPrs={prs.length}/>);
        });
        return tableRows;
      },

      render: function() {
        return (
          <div className='container'>
            <h3>All Users</h3>
            <TableView
              rows={this.tableRows()}
              columnNames={this.columnNames}
              sortFunctions={this.sortFunctions}
              initialSortCol="Open PRs"
              initialSortDirection="desc"/>
          </div>
          );
      }
    });

    return UsersPage;
  }
);
