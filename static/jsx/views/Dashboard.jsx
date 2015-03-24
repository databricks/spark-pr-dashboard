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

    var Dashboard = React.createClass({
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
        var hash = window.location.hash.split('#');
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
            <SubNavigation
              prs={this.state.prs}
              active={this.state.activeTab}/>);
          mainView = (
            <div className="container-fluid">
              <PRTableView
                prs={this.state.currentPrs}
                showJenkinsButtons={this.props.showJenkinsButtons}/>
            </div>);
        } else {
          mainView = (
            <div className="container-fluid">
              <div className="jumbotron text-center loading-icon">
                <span className="glyphicon glyphicon-refresh"></span>
                <h2>Loading PRs</h2>
              </div>
            </div>
          );
        }

        return (
          <div>
            {subNavigation}
            {mainView}
          </div>
        );
      }
    });


    return Dashboard;
  }
);
