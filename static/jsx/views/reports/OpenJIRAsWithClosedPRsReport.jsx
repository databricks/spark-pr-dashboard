define([
    'react',
    'jquery',
    'underscore',
    'views/TableView'
  ],
  function(React, $, _, TableView) {
    'use strict';

    var JIRATableRow = React.createClass({
      render: function() {
        var href = 'http://issues.apache.org/jira/browse/' + this.props.jira.id;
        return (
          <tr>
            <td><a href={href} target="_blank">{this.props.jira.id}</a></td>
            <td><a href={href} target="_blank">{this.props.jira.summary}</a></td>
          </tr>
        );
      }
    });

    var OpenJIRAsWithClosedPRsReport = React.createClass({

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
          return (<JIRATableRow key={jira.id} jira={jira}/>);
        });
        return tableRows;
      },

      viewContents: function() {
        if (this.state.jiras === null) {
          return (<p>Loading...</p>);
        } else {
          return (
            <TableView
            rows={this.tableRows()}
            columnNames={this.columnNames}
            sortFunctions={this.sortFunctions}
            initialSortCol="JIRA Id"
            initialSortDirection="desc"/>
          );
        }
      },

      render: function() {
        console.log("called render!");
        return (
          <div className='container'>
            <h3>Open JIRA issues with closed pull requests</h3>
            {this.viewContents()}
          </div>
        );
      }
    });

    return OpenJIRAsWithClosedPRsReport;
  }
);
