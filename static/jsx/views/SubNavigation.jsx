define([
    'react',
    'mixins/UrlMixin'
  ],
  function(React, UrlMixin) {
    "use strict";

    var SubNavigationItem = React.createClass({
      mixins: [UrlMixin],
      onClick: function(event) {
        var component = this.props.component;
        this.pushAnchor(component);
      },

      render: function() {
        return (
          <li className={this.props.active ? "subnav-active" : ""}>
            <a onClick={this.onClick}>
              {this.props.label}
            </a>
          </li>
        );
      }
    });

    var SubNavigation = React.createClass({
      getDefaultProps: function() {
        return {prsCountByGroup: []};
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

          navigationItems.push(<SubNavigationItem
            key={item.component}
            component={item.component}
            label={label}
            active={item.component === this.props.active}/>);
        }

        return (
          <nav className="sub-nav navbar navbar-default"
            role="navigation">
            <div className="container-fluid">
              <ul className="nav navbar-nav">
                {navigationItems}
              </ul>
            </div>
          </nav>
        );
      }
    });

    return SubNavigation;
  }
);
