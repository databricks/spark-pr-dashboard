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

    var JIRALink = React.createClass({
      render: function() {
        var link = "http://issues.apache.org/jira/browse/SPARK-" + this.props.number;
        var className = "jira-link";
        if (this.props.isClosed) {
          className += " label label-pill label-danger";
        }
        return (
          <a className={className} href={link} target="_blank">
            {this.props.number}
          </a>
        );
      }
    });

    var Commenter = React.createClass({
      componentDidMount: function() {
        var _this = this;
        $(this.refs.commenter.getDOMNode()).popover({
          trigger: "focus",
          placement: "left",
          html: true,
          title: function() {
            var postTime = _this.props.comment.date[0];
            return "<a href='" + _this.props.comment.url + "'>Comment</a> from <a href='/users/" +
              _this.props.username + "'>" + _this.props.username + "</a>, posted " +
              "<abbr title='" + postTime + "'>" + $.timeago(postTime) + "</abbr>";
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
        }).click(function(e) {
           // Hack to fix comment popovers in Firefox.
           e.preventDefault();
           $(this).focus();
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
          <img
            src={comment.avatar + "&s=16"}
            alt={username}
            ref="commenter"
            tabIndex="0"
            className={commenterClass}/>
        );
      }
    });

    var TestWithJenkinsButton = React.createClass({
      onClick: function() {
        var prNum = this.props.pr.number;
        var shouldTest = confirm("Are you sure you want to test PR " + prNum + " with Jenkins?");
        if (shouldTest) {
          window.open('/trigger-jenkins/' + prNum, '_blank');
        }
      },
      render: function() {
        return (
          <button
            onClick={this.onClick}
            className="btn btn-default btn-xs">
            <span className="glyphicon glyphicon-refresh"></span>
            Test
          </button>
        );
      }
    });

    var PRTableRow = React.createClass({
      componentDidMount: function() {
        if (this.refs.jenkinsPopover !== undefined) {
          $(this.refs.jenkinsPopover.getDOMNode()).popover();
        }
      },

      render: function() {
        var pr = this.props.pr;
        var jiraLinkRows = _.map(pr.parsed_title.jiras, function(number) {
          var isClosed = $.inArray(number, pr.closed_jiras) !== -1;
          return (<li><JIRALink key={number} number={number} isClosed={isClosed}/></li>);
        });
        var jiraLinks = <ul className="jira-links-list">{jiraLinkRows}</ul>;

        var targetVersionRows =  _.map(pr.jira_target_versions, function(version) {
          return (<li>{version}</li>);
        });
        var targetVersions = <ul className="jira-links-list">{targetVersionRows}</ul>;

        var commenters = _.map(pr.commenters, function(comment) {
          return (
            <Commenter
              key={comment.data.date}
              username={comment.username}
              comment={comment.data}/>
          );
        });

        var mergeIcon = (pr.is_mergeable ?
          <i className="glyphicon glyphicon-ok"></i> :
          <i className="glyphicon glyphicon-remove"></i>);

        var pullLink = "https://github.com/apache/spark/pull/" + pr.number;

        var jenkinsOutcome = jenkinsOutcomes[pr.last_jenkins_outcome];
        var iconClass = "glyphicon glyphicon-" + jenkinsOutcome.iconName;

        var jenkinsCell;
        var lastJenkinsComment = pr.last_jenkins_comment;
        if (lastJenkinsComment) {
          var username = lastJenkinsComment.user.login;
          var postTime = lastJenkinsComment.date[0];
          var title = "<a href='" + lastJenkinsComment.html_url + "'>Comment</a> from " +
            "<a href='/users/" + username + "'>" + username + "</a>, posted " +
             "<abbr title='" + postTime + "'>" + $.timeago(postTime) + "</abbr>";
          var content = marked(lastJenkinsComment.body);

          jenkinsCell = (
            <span ref="jenkinsPopover" tabIndex="0"
              data-toggle="popover" data-trigger="focus"
              data-placement="left" data-html="true"
              data-title={title} data-content={content}>
              <i className={iconClass}></i>
              <span className="jenkins-outcome-link">
                {jenkinsOutcome.label}
              </span>
            </span>
          );
        } else {
          jenkinsCell = (
            <div>
              <i className={iconClass}></i>
              {jenkinsOutcome.label}
            </div>
          );
        }

        var updatedAt = $.timeago(pr.updated_at + "Z");
        var updatedCell = <abbr title={pr.updated_at}>{updatedAt}</abbr>;

        var updatedByCommitterCell;
        if (pr.updated_by_committer_at) {
          var updatedByCommitterAt = $.timeago(pr.updated_by_committer_at);
          updatedByCommitterCell =
            <abbr title={pr.updated_by_committer_at}>{updatedByCommitterAt}</abbr>;
        }
        var toolsCell =
          <td>
            <TestWithJenkinsButton pr={pr}/>
          </td>;
        return (
          <tr>
            {this.props.showJenkinsButtons ? toolsCell : ""}
            <td>
              <a href={pullLink} target="_blank">
              {pr.number}
              </a>
            </td>
            <td>{jiraLinks}</td>
            <td>
              <img
                src={pr.jira_priority_icon_url}
                title={pr.jira_priority_name}
                alt={pr.jira_priority_name}/>
            </td>
            <td>
              <img
                src={pr.jira_issuetype_icon_url}
                title={pr.jira_issuetype_name}
                alt={pr.jira_issuetype_name}/>
            </td>
            <td>
              {targetVersions}
            </td>
            <td>
              <a href={pullLink} target="_blank">
                {pr.parsed_title.metadata + pr.parsed_title.title}
              </a>
            </td>
            <td>
              <a href={"/users/" + pr.user}>
                {pr.user}
              </a>
            </td>
            <td>
              <span>{pr.jira_shepherd_display_name}</span>
            </td>
            <td>
              {commenters}
            </td>
            <td>
              <span className="lines-added">+{pr.lines_added}</span>
              <span className="lines-deleted">-{pr.lines_deleted}</span>
            </td>
            <td>
              {mergeIcon}
            </td>
            <td>
              {jenkinsCell}
            </td>
            <td>
              {updatedCell}
            </td>
            <td>
              {updatedByCommitterCell}
            </td>
          </tr>
        );
      }
    });

    var PRTableView = React.createClass({
      propTypes: {
        prs: React.PropTypes.array.isRequired
      },

      sortFunctions: {
        'Number': function(row) { return row.props.pr.number; },
        'JIRAs': function(row) { return row.props.pr.parsed_title.jiras; },
        'Priority': function(row) { return row.props.pr.jira_priority_name; },
        'Issue Type': function(row) { return row.props.pr.jira_issuetype_name; },
        'Target Versions': function(row) { return row.props.pr.jira_target_versions || 'A'; },
        'Title': function(row) { return row.props.pr.parsed_title.title.toLowerCase(); },
        'Author': function(row) { return row.props.pr.user.toLowerCase(); },
        'Shepherd': function(row) { return row.props.pr.jira_shepherd_display_name || ''; },
        'Commenters': function(row) { return row.props.pr.commenters.length; },
        'Changes': function(row) { return row.props.pr.lines_changed; },
        'Merges': function(row) { return row.props.pr.is_mergeable; },
        'Jenkins': function(row) { return row.props.pr.last_jenkins_outcome; },
        'Updated': function(row) { return row.props.pr.updated_at; },
        'Updated by Committer': function(row) { return row.props.pr.updated_by_committer_at; }
      },

      columnNames: function() {
        var columNames = [
          "Number",
          "JIRAs",
          "Priority",
          "Issue Type",
          "Target Versions",
          "Title",
          "Author",
          "Shepherd",
          "Commenters",
          "Changes",
          "Merges",
          "Jenkins",
          "Updated",
          "Updated by Committer"
        ];
        if (this.props.showJenkinsButtons) {
          columNames.unshift("Tools");
        }
        return columNames;
      },

      render: function() {
        var _this = this;
        var tableRows = _.map(this.props.prs, function(pr) {
          return (
            <PRTableRow
              key={pr.number}
              pr={pr}
              showJenkinsButtons={_this.props.showJenkinsButtons}/>
          );
        });

        return (
          <TableView
            rows={tableRows}
            columnNames={this.columnNames()}
            sortFunctions={this.sortFunctions}/>
        );
      }
    });

    return PRTableView;
  }
);
