// jscs:disable
define([
    'react',
    'react-mini-router',
    'jquery',
    'underscore',
    'marked',
    'bootstrap',
    'jquery-timeago'
  ],
  function(React, Router, $, _, marked) {
    "use strict";

    var navigate = Router.navigate;
    // jscs:enable

    var jenkinsOutcomes = {
      Pass: {label: "Passed", iconName: "ok"},
      Fail: {label: "Failed", iconName: "remove"},
      Timeout: {label: "Timed out", iconName: "time"},
      Running: {label: "Running", iconName: "arrow-right"},
      Verify: {label: "Admin needed", iconName: "comment"},
      Asked: {label: "Asked to test", iconName: "comment"},
      Unknown: {label: "Unknown", iconName: "question-sign"}
    };

    var JIRALink = React.createClass({displayName: 'JIRALink',
      render: function() {
        var link = "http://issues.apache.org/jira/browse/SPARK-" + this.props.number;
        return (
          React.createElement("a", {href: link, target: "_blank"}, 
            this.props.number
          )
        );
      }
    });

    var Commenter = React.createClass({displayName: 'Commenter',
      componentDidMount: function() {
        $(this.refs.commenter.getDOMNode()).popover();
      },

      render: function() {
        var comment = this.props.comment;
        var username = this.props.username;
        var commenterClass = "commenter commenter-icon";

        if (comment.said_lgtm) {
          commenterClass += " lgtm";
        } else if (comment.asked_to_close) {
          commenterClass += " asked-to-close";
        }

        var title = "<a href='" + comment.url + "'>Comment</a> from <a href='/users/" +
          username + "'>" + username + "</a>";
        var content = marked(comment.body);

        return (
          React.createElement("img", {ref: "commenter", tabIndex: "0", className: commenterClass, 
            src: comment.avatar + "&s=16", alt: username, 'data-toggle': "popover", 
            'data-trigger': "focus", 'data-placement': "left", 'data-html': "true", 
            'data-title': title, 'data-content': content})
        );
      }
    });

    var TestWithJenkinsButton = React.createClass({displayName: 'TestWithJenkinsButton',
      onClick: function() {
        var prNum = this.props.pr.number;
        var shouldTest = confirm("Are you sure you want to test PR " + prNum + " with Jenkins?");
        if (shouldTest) {
          window.open('/trigger-jenkins/' + prNum, '_blank');
        }
      },
      render: function() {
        return (
          React.createElement("button", {
            onClick: this.onClick, 
            className: "btn btn-default btn-xs"}, 
            React.createElement("span", {className: "glyphicon glyphicon-refresh"}), 
            "Test with Jenkins"
          )
        );
      }
    });

    var PRTableColumnHeader = React.createClass({displayName: 'PRTableColumnHeader',
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
          return React.createElement("span", null, " ▾");
        } else if (this.props.sortDirection === 'desc') {
          return React.createElement("span", null, " ▴");
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

    var PRTableRow = React.createClass({displayName: 'PRTableRow',
      componentDidMount: function() {
        if (this.refs.jenkinsPopover != undefined) {
          $(this.refs.jenkinsPopover.getDOMNode()).popover();
        }
      },

      render: function() {
        var pr = this.props.pr;
        var jiraLinks = _.map(pr.parsed_title.jiras, function(number) {
          return React.createElement(JIRALink, {key: number, number: number});
        });

        var commenters = _.map(pr.commenters, function(comment) {
          return (
            React.createElement(Commenter, {
              key: comment.data.date, 
              username: comment.username, 
              comment: comment.data})
          );
        });

        var mergeIcon = (pr.is_mergeable ?
          React.createElement("i", {className: "glyphicon glyphicon-ok"}) :
          React.createElement("i", {className: "glyphicon glyphicon-remove"}));

        var pullLink = "https://www.github.com/apache/spark/pull/" + pr.number;

        var jenkinsOutcome = jenkinsOutcomes[pr.last_jenkins_outcome];
        var iconClass = "glyphicon glyphicon-" + jenkinsOutcome.iconName;

        var jenkinsCell;
        var lastJenkinsComment = pr.last_jenkins_comment;
        if (lastJenkinsComment) {
          var username = lastJenkinsComment.user.login;
          var title = "<a href='" + lastJenkinsComment.html_url + "'>Comment</a> from " +
            "<a href='/users/" + username + "'>" + username + "</a>";
          var content = marked(lastJenkinsComment.body);

          jenkinsCell = (
            React.createElement("span", {ref: "jenkinsPopover", tabIndex: "0", 
              'data-toggle': "popover", 'data-trigger': "focus", 
              'data-placement': "left", 'data-html': "true", 
              'data-title': title, 'data-content': content}, 
              React.createElement("i", {className: iconClass}), 
              React.createElement("span", {className: "jenkins-outcome-link"}, 
                jenkinsOutcome.label
              )
            )
          );
        } else {
          jenkinsCell = (
            React.createElement("div", null, 
              React.createElement("i", {className: iconClass}), 
              jenkinsOutcome.label
            )
          );
        }

        var updatedAt = $.timeago(pr.updated_at + "Z");
        var updatedCell = React.createElement("abbr", {title: pr.updated_at}, updatedAt);
        var toolsCell =
          React.createElement("td", null, 
            React.createElement(TestWithJenkinsButton, {pr: pr})
          );
        return (
          React.createElement("tr", null, 
            React.createElement("td", null, 
              React.createElement("a", {href: pullLink, target: "_blank"}, 
              pr.number
              )
            ), 
            React.createElement("td", null, jiraLinks), 
            React.createElement("td", null, 
              React.createElement("a", {href: pullLink, target: "_blank"}, 
                pr.parsed_title.metadata + pr.parsed_title.title
              )
            ), 
            React.createElement("td", null, 
              React.createElement("a", {href: "/users/" + pr.user}, 
                pr.user
              )
            ), 
            React.createElement("td", null, 
              commenters
            ), 
            React.createElement("td", null, 
              React.createElement("span", {className: "lines-added"}, "+", pr.lines_added), 
              React.createElement("span", {className: "lines-deleted"}, "-", pr.lines_deleted)
            ), 
            React.createElement("td", null, 
              mergeIcon
            ), 
            React.createElement("td", null, 
              jenkinsCell
            ), 
            React.createElement("td", null, 
              updatedCell
            ), 
            this.props.showJenkinsButtons ? toolsCell : ""
          )
        );
      }
    });

    var PRTableView = React.createClass({displayName: 'PRTableView',
      propTypes: {
        prs: React.PropTypes.array.isRequired
      },
      getInitialState: function() {
        return {sortCol: '', sortDirection: 'unsorted'}
      },
      componentWillMount: function() {
        this.doSort(this.state.sortCol, this.state.sortDirection, this.props.prs);
      },
      componentWillReceiveProps: function(newProps) {
        this.doSort(this.state.sortCol, this.state.sortDirection, newProps.prs);
      },
      sortFunctions:  {
        'Number': function(pr) { return pr.number; },
        'JIRAs': function(pr) { return pr.parsed_title.jiras; },
        'Title': function(pr) { return pr.parsed_title.metadata + pr.parsed_title.title; },
        'Author': function(pr) { return pr.user.toLowerCase(); },
        'Commenters': function(pr) { return pr.commenters.length; },
        'Changes': function(pr) { return pr.lines_changed; },
        'Merges': function(pr) { return pr.is_mergeable; },
        'Jenkins': function(pr) { return pr.last_jenkins_outcome; },
        'Updated': function(pr) { return pr.updated_at; }
      },
      doSort: function(sortCol, sortDirection, sortedPrs) {
        // Sort the PRs in this table and update its state
        var newSortedPrs = _.sortBy(sortedPrs, this.sortFunctions[sortCol]);
        if (sortDirection === 'desc') {
          newSortedPrs.reverse();
        }
        this.setState({sortCol: sortCol, sortDirection: sortDirection, sortedPrs: newSortedPrs});
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
          sortDirection = 'desc'
        }
        this.doSort(sortCol, sortDirection, this.state.sortedPrs);
      },
      render: function() {
        var _this = this;
        var tableRows = _.map(this.state.sortedPrs, function(pr) {
          return (
            React.createElement(PRTableRow, {
              key: pr.number, 
              pr: pr, 
              showJenkinsButtons: _this.props.showJenkinsButtons})
          )
        });
        var outer = this;
        var columNames = [
          "Number",
          "JIRAs",
          "Title",
          "Author",
          "Commenters",
          "Changes",
          "Merges",
          "Jenkins",
          "Updated"];
        if (this.props.showJenkinsButtons) {
          columNames.push("Tools");
        }
        var tableHeaders = _.map(columNames, function(colName) {
          var sortDirection = (colName === outer.state.sortCol ?
            outer.state.sortDirection :
            'unsorted');

          return (
            React.createElement(PRTableColumnHeader, {
              key: colName, 
              name: colName, 
              onSort: outer.onSort, 
              sortDirection: sortDirection}));
        });
        return (
          React.createElement("table", {className: "table table-condensed"}, 
            React.createElement("tbody", null, 
              React.createElement("tr", null, tableHeaders), 
              tableRows
            )
          )
        );
      }
    });

    return PRTableView;
  }
);
