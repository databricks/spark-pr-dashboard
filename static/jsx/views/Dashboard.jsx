// jscs:disable
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

    // jscs:enable
    var Dashboard = React.createClass({
      mixins: [UrlMixin],
      getInitialState: function() {
        return {prs: [], activeTab: '', currentPrs: []};
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
        if (prevState.activeTab !== this.state.activeTab) {
          this._filterPrsByComponent(this.state.activeTab);
        }
      },

      _filterPrsByComponent: function(component) {
        var neededPrs = [],
            prs = this.state.prs;

        for (var i = 0; i < prs.length; i++) {
          if (prs[i].component == component) {
            neededPrs = prs[i].prs;
            break;
          }
        }

        this.setState({activeTab: component, currentPrs: neededPrs});
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
          return {component: component, prs: prs, count: prs.length}
        });

        var tab = this._checkTabAvailability(prsByComponent);

        this.setState({prs: result, activeTab: tab ? tab : mainTab});
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
              active={this.state.activeTab}
              onClick={this._filterPrsByComponent}/>);
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
          )
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
