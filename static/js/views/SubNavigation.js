// jscs:disable
define([
    'react',
    'mixins/UrlMixin'
  ],
  function(React, UrlMixin) {
    "use strict";


    // jscs:enable
    var SubNavigationItem = React.createClass({displayName: 'SubNavigationItem',
      mixins: [UrlMixin],
      onClick: function(event) {
        var component = this.props.component;
        this.pushAnchor(component);
        this.props.onClick(component);
      },

      render: function() {
        return (
          React.createElement("li", {className: this.props.active ? "subnav-active" : ""}, 
            React.createElement("a", {onClick: this.onClick}, 
              this.props.label
            )
          )
        );
      }
    });

    var SubNavigation = React.createClass({displayName: 'SubNavigation',
      getDefaultProps: function() {
        return {prsCountByGroup: []};
      },

      _onClick: function(component) {
        this.props.onClick(component);
      },

      render: function() {
        var navigationItems = [],
          prs = this.props.prs;

        prs.sort(function(pr1, pr2) {
          return pr2.count - pr1.count;
        });

        for (var i = 0; i < prs.length; i++) {
          var item = prs[i];
          var label = item.component + " (" + item.count + ")";

          navigationItems.push(React.createElement(SubNavigationItem, {
            key: item.component, 
            component: item.component, 
            label: label, 
            active: item.component == this.props.active, 
            onClick: this._onClick}));
        }

        return (
          React.createElement("nav", {className: "sub-nav navbar navbar-default", 
            role: "navigation"}, 
            React.createElement("div", {className: "container-fluid"}, 
              React.createElement("ul", {className: "nav navbar-nav"}, 
                navigationItems
              )
            )
          )
        );
      }
    });

    return SubNavigation;
  }
);
