define([
    'react',
    'react-mini-router',
    'jquery',
    'underscore',
    'marked',
    'views/TableView',
    'bootstrap',
    'jquery-timeago'
  ],
  function(React, Router, $, _, marked, TableView) {
    "use strict";

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
          React.createElement("a", {className: "jira-link", href: link, target: "_blank"}, 
            this.props.number
          )
        );
      }
    });

    var Commenter = React.createClass({displayName: 'Commenter',
      componentDidMount: function() {
        var _this = this;
        $(this.refs.commenter.getDOMNode()).popover({
          trigger: "focus",
          placement: "left",
          html: true,
          title: function() {
            return "<a href='" + _this.props.comment.url + "'>Comment</a> from <a href='/users/" +
              _this.props.username + "'>" + _this.props.username + "</a>";
          },
          content: function() {
            var rendered_markdown = marked(_this.props.comment.body);
            var diff_hunk = _this.props.comment.diff_hunk;
            if (diff_hunk !== '') {
              var div = $('<div></div>');
              div.append($('<pre></pre>').text(diff_hunk));
              div.append($(rendered_markdown));
              return div;
            } else {
              return rendered_markdown;
            }
          }
        });
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

        return (
          React.createElement("img", {
            src: comment.avatar + "&s=16", 
            alt: username, 
            ref: "commenter", 
            tabIndex: "0", 
            className: commenterClass})
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

    var ReviewStatusCell = React.createClass({displayName: 'ReviewStatusCell',
      getInitialState: function() {
        return {value: this.props.pr.review_status};
      },
      onChange: function(event) {
        var newValue = event.target.value;
        if (newValue !== this.state.value) {
          console.log("Updating state for PR " + this.props.pr.number + " to '" + newValue + "'");
          this.props.pr.review_status = newValue;
          this.setState({value: newValue});
        }
      },
      render: function() {
          return (
            React.createElement("select", {className: "form-control", onChange: this.onChange, value: this.state.value}, 
              React.createElement("option", null, "Review needed"), 
              React.createElement("option", null, "Update needed")
            )
          );
      }
    });

    var PRTableRow = React.createClass({displayName: 'PRTableRow',
      componentDidMount: function() {
        if (this.refs.jenkinsPopover !== undefined) {
          $(this.refs.jenkinsPopover.getDOMNode()).popover();
        }
      },

      render: function() {
        var pr = this.props.pr;
        var jiraLinks = _.map(pr.parsed_title.jiras, function(number) {
          return (React.createElement(JIRALink, {key: number, number: number}));
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

        var pullLink = "https://github.com/apache/spark/pull/" + pr.number;

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
        var rowClass = pr.review_status === "Update needed" ? "muted-row" : "";
        return (
          React.createElement("tr", {className: rowClass}, 
            React.createElement("td", null, 
              React.createElement("a", {href: pullLink, target: "_blank"}, 
              pr.number
              )
            ), 
            React.createElement("td", null, jiraLinks), 
            React.createElement("td", null, 
              React.createElement("img", {
                src: pr.jira_priority_icon_url, 
                title: pr.jira_priority_name, 
                alt: pr.jira_priority_name})
            ), 
            React.createElement("td", null, 
              React.createElement("img", {
                src: pr.jira_issuetype_icon_url, 
                title: pr.jira_issuetype_name, 
                alt: pr.jira_issuetype_name})
            ), 
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
            React.createElement("td", null, commenters), 
            React.createElement("td", null, 
              React.createElement("span", {className: "lines-added"}, "+", pr.lines_added), 
              React.createElement("span", {className: "lines-deleted"}, "-", pr.lines_deleted)
            ), 
            React.createElement("td", null, mergeIcon), 
            React.createElement("td", null, jenkinsCell), 
            React.createElement("td", null, React.createElement(ReviewStatusCell, {pr: pr})), 
            React.createElement("td", null, updatedCell), 
            this.props.showJenkinsButtons ? toolsCell : ""
          )
        );
      }
    });

    var PRTableView = React.createClass({displayName: 'PRTableView',
      propTypes: {
        prs: React.PropTypes.array.isRequired
      },

      sortFunctions: {
        'Number': function(row) { return row.props.pr.number; },
        'JIRAs': function(row) { return row.props.pr.parsed_title.jiras; },
        'Priority': function(row) { return row.props.pr.jira_priority_name; },
        'Issue Type': function(row) { return row.props.pr.jira_issuetype_name; },
        'Title': function(row) { return row.props.pr.parsed_title.title.toLowerCase(); },
        'Author': function(row) { return row.props.pr.user.toLowerCase(); },
        'Commenters': function(row) { return row.props.pr.commenters.length; },
        'Changes': function(row) { return row.props.pr.lines_changed; },
        'Merges': function(row) { return row.props.pr.is_mergeable; },
        'Jenkins': function(row) { return row.props.pr.last_jenkins_outcome; },
        'Review Status': function(row) { return "Waiting on author"; },
        'Updated': function(row) { return row.props.pr.updated_at; }
      },

      columnNames: function() {
        var columNames = [
          "Number",
          "JIRAs",
          "Priority",
          "Issue Type",
          "Title",
          "Author",
          "Commenters",
          "Changes",
          "Merges",
          "Jenkins",
          "Review Status",
          "Updated"
        ];
        if (this.props.showJenkinsButtons) {
          columNames.push("Tools");
        }
        return columNames;
      },

      render: function() {
        var _this = this;
        var tableRows = _.map(this.props.prs, function(pr) {
          return (
            React.createElement(PRTableRow, {
              key: pr.number, 
              pr: pr, 
              showJenkinsButtons: _this.props.showJenkinsButtons})
          );
        });

        return (
          React.createElement(TableView, {
            rows: tableRows, 
            columnNames: this.columnNames(), 
            sortFunctions: this.sortFunctions})
        );
      }
    });

    return PRTableView;
  }
);
