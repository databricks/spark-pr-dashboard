define([
    'react',
    'jquery',
    'underscore',
    'views/TableView'
  ],
  function(React, $, _, TableView) {
    'use strict';

    var JIRATableRow = React.createClass({displayName: 'JIRATableRow',
      render: function() {
        var href = 'http://issues.apache.org/jira/browse/' + this.props.jira.id;
        return (
          React.createElement("tr", null, 
            React.createElement("td", null, React.createElement("a", {href: href, target: "_blank"}, this.props.jira.id)), 
            React.createElement("td", null, React.createElement("a", {href: href, target: "_blank"}, this.props.jira.summary))
          )
        );
      }
    });

    var OpenJIRAsWithClosedPRsReport = React.createClass({displayName: 'OpenJIRAsWithClosedPRsReport',

      getInitialState: function() {
        return {jiras: null};
      },

      componentDidMount: function() {
        var _this = this;

        $.ajax({
          url: '/reports/open-jira-issues-with-closed-prs.json',
          dataType: 'json',
          success: function(jiras) {
            if (_this.isMounted()) {
              _this.setState({jiras: jiras});
            }
          }
        });
      },

      columnNames: ['JIRA Id', 'Summary'],

      sortFunctions: {
        'JIRA Id': function(row) { return row.props.jira.id; },
        'Summary': function(row) { return row.props.jira.summary; }
      },

      tableRows: function() {
        var tableRows = _.map(this.state.jiras, function(jira) {
          return (React.createElement(JIRATableRow, {key: jira.id, jira: jira}));
        });
        return tableRows;
      },

      viewContents: function() {
        if (this.state.jiras === null) {
          return (React.createElement("p", null, "Loading..."));
        } else {
          return (
            React.createElement(TableView, {
            rows: this.tableRows(), 
            columnNames: this.columnNames, 
            sortFunctions: this.sortFunctions, 
            initialSortCol: "JIRA Id", 
            initialSortDirection: "desc"})
          );
        }
      },

      render: function() {
        console.log("called render!");
        return (
          React.createElement("div", {className: "container"}, 
            React.createElement("h3", null, "Open JIRA issues with closed pull requests"), 
            this.viewContents()
          )
        );
      }
    });

    return OpenJIRAsWithClosedPRsReport;
  }
);
