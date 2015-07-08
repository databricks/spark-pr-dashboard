define([
    'react',
    'jquery',
    'underscore'
  ],
  function(React, $, _) {
    "use strict";

    var ColumnHeader = React.createClass({displayName: "ColumnHeader",
      propTypes: {
        name: React.PropTypes.string.isRequired,
        sortable: React.PropTypes.bool.isRequired,
        onSort: React.PropTypes.func.isRequired,
        sortDirection: React.PropTypes.oneOf(['asc', 'desc', 'unsorted'])
      },
      getDefaultProps: function() {
        return {
          sortable: true,
          sortDirection: 'unsorted'
        };
      },
      sortDirectionIndicator: function() {
        if (this.props.sortDirection === 'asc') {
          return (React.createElement("span", null, " ▾"));
        } else if (this.props.sortDirection === 'desc') {
          return (React.createElement("span", null, " ▴"));
        } else {
          return '';
        }
      },
      onSort: function() {
        this.props.onSort(this.props.name);
      },
      render: function() {
        return (
          React.createElement("th", {onClick: this.onSort}, 
            this.props.name, this.sortDirectionIndicator()
          )
          );
      }
    });

    /**
     * A table view that supports customizable per-column sorting.
     */
    var TableView = React.createClass({displayName: "TableView",
      propTypes: {
        rows: React.PropTypes.arrayOf(React.PropTypes.element).isRequired,
        columnNames: React.PropTypes.arrayOf(React.PropTypes.string).isRequired,
        sortFunctions: React.PropTypes.objectOf(React.PropTypes.func).isRequired,
        initialSortCol: React.PropTypes.string,
        initialSortDirection: React.PropTypes.string,
      },

      getInitialState: function() {
        return {
          sortCol: this.props.initialSortCol || '',
          sortDirection: this.props.initialSortDirection || 'unsorted'
        };
      },

      componentWillMount: function() {
        this.doSort(this.state.sortCol, this.state.sortDirection, this.props.rows);
      },

      componentWillReceiveProps: function(newProps) {
        this.doSort(this.state.sortCol, this.state.sortDirection, newProps.rows);
      },

      doSort: function(sortCol, sortDirection, sortedRows) {
        // Sort the rows in this table and update its state
        var newSortedRows = _.sortBy(sortedRows, this.props.sortFunctions[sortCol]);
        if (sortDirection === 'desc') {
          newSortedRows.reverse();
        }
        this.setState({sortCol: sortCol, sortDirection: sortDirection, sortedRows: newSortedRows});
      },

      onSort: function(sortCol) {
        // Callback when a user clicks on a column header to perform a sort.
        // Handles the logic of toggling sort directions
        var sortDirection;
        if (sortCol === this.state.sortCol) {
          if (this.state.sortDirection === 'unsorted' || this.state.sortDirection === 'asc') {
            sortDirection = 'desc';
          } else if (this.state.sortDirection === 'desc') {
            sortDirection = 'asc';
          }
        } else {
          sortDirection = 'desc';
        }
        this.doSort(sortCol, sortDirection, this.state.sortedRows);
      },

      render: function() {
        var _this = this;
        var tableHeaders = _.map(this.props.columnNames, function(colName) {
          var sortDirection = (colName === _this.state.sortCol ?
            _this.state.sortDirection :
            'unsorted');

          return (
            React.createElement(ColumnHeader, {
              key: colName, 
              name: colName, 
              onSort: _this.onSort, 
              sortDirection: sortDirection}));
        });
        return (
          React.createElement("table", {className: "table table-condensed table-hover"}, 
            React.createElement("thead", null, 
              React.createElement("tr", null, tableHeaders)
            ), 
            React.createElement("tbody", null, 
              this.state.sortedRows
            )
          )
        );
      }
    });

    return TableView;
  }
);
