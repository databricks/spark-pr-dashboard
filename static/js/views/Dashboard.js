define([
    'react',
    'jquery',
    'underscore',
    'views/SubNavigation',
    'views/PRTableView',
    'mixins/UrlMixin'
  ],
  function(React, $, _, SubNavigation, PRTableView, UrlMixin) {
    "use strict";

    var Dashboard = React.createClass({displayName: "Dashboard",
      mixins: [UrlMixin],
      getInitialState: function() {
        return {prs: [], prsByComponent: {}, activeTab: '', currentPrs: []};
      },

      componentDidMount: function() {
        if (this.props.prs.length > 0) {
          this._prepareData(this.props.prs);
        }
      },

      componentWillReceiveProps: function(nextProps) {
        this._prepareData(nextProps.prs);
      },

      componentDidUpdate: function(prevProps, prevState) {
        var newActiveTab = this.state.activeTab;
        if (prevState.activeTab !== newActiveTab || prevState.prs !== this.state.prs) {
          this.setState({
            activeTab: newActiveTab,
            currentPrs: this.state.prsByComponent[newActiveTab] || []
          });
        }
      },

      _prepareData: function(prs) {
        var prsByComponent = {}, mainTab = "All";
        for (var i = 0; i < prs.length; i++) {
          var pr = prs[i];
          if (!prsByComponent.hasOwnProperty(mainTab)) {
            prsByComponent[mainTab] = [];
          }
          for (var j = 0; j < pr.components.length; j++) {
            var component = pr.components[j];
            if (!prsByComponent.hasOwnProperty(component)) {
              prsByComponent[component] = [];
            }
            prsByComponent[component].push(pr);
          }
          prsByComponent[mainTab].push(pr);
        }

        var result = _.map(prsByComponent, function(prs, component) {
          return {component: component, prs: prs, count: prs.length};
        });

        var tab = this._checkTabAvailability(prsByComponent);

        this.setState({
          prs: result,
          activeTab: tab ? tab : mainTab,
          prsByComponent: prsByComponent
        });
      },

      _checkTabAvailability: function(prsByComponent) {
        var hash = window.location.hash.split(/#|&/);
        var anchor = hash.pop();

        for (var component in prsByComponent) {
          if (this.getAnchor(component) === anchor) {
            return component;
          }
        }
      },

      render: function() {
        var subNavigation, mainView;
        if (this.state.prs.length > 0) {
          subNavigation = (
            React.createElement(SubNavigation, {
              prs: this.state.prs, 
              active: this.state.activeTab}));
          mainView = (
            React.createElement("div", {className: "container-fluid"}, 
              React.createElement(PRTableView, {
                prs: this.state.currentPrs, 
                showJenkinsButtons: this.props.showJenkinsButtons})
            ));
        } else {
          mainView = (
            React.createElement("div", {className: "container-fluid"}, 
              React.createElement("div", {className: "jumbotron text-center loading-icon"}, 
                React.createElement("span", {className: "glyphicon glyphicon-refresh"}), 
                React.createElement("h2", null, "Loading PRs")
              )
            )
          );
        }

        return (
          React.createElement("div", null, 
            subNavigation, 
            mainView
          )
        );
      }
    });


    return Dashboard;
  }
);
