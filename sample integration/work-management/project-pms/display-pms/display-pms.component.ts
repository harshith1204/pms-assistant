import { Component } from '@angular/core';

interface DisplayProperty {
  name: string;
  selected: boolean;
}

interface GroupByOption {
  name: string;
  checked: boolean;
}

interface OrderByOption {
  name: string;
  checked: boolean;
}

@Component({
  selector: 'app-display-pms',
  templateUrl: './display-pms.component.html',
  styleUrls: ['./display-pms.component.scss']
})
export class DisplayPmsComponent {
  displayProperties: DisplayProperty[] = [
    { name: 'ID', selected: false },
    { name: 'Assignee', selected: false },
    { name: 'Start date', selected: false },
    { name: 'Due date', selected: false },
    { name: 'Labels', selected: false },
    { name: 'Priority', selected: false },
    { name: 'State', selected: false },
    { name: 'Sub-work item count', selected: false },
    { name: 'Attachment count', selected: false },
    { name: 'Link', selected: false },
    { name: 'Estimate', selected: false },
    { name: 'Module', selected: false },
    { name: 'Cycle', selected: false }
  ];

  groupByOptions: GroupByOption[] = [
    { name: 'States', checked: true },
    { name: 'Priority', checked: false },
    { name: 'Cycle', checked: false },
    { name: 'Module', checked: false },
    { name: 'Labels', checked: false },
    { name: 'Assignees', checked: false },
    { name: 'Created by', checked: false },
    { name: 'None', checked: false }
  ];

  orderByOptions: OrderByOption[] = [
    { name: 'Manual', checked: true },
    { name: 'Last created', checked: false },
    { name: 'Last updated', checked: false },
    { name: 'Start date', checked: false },
    { name: 'Due date', checked: false },
    { name: 'Priority', checked: false }
  ];

  showSubWorkItems = false;
  showEmptyGroups = false;

  toggleProperty(prop: DisplayProperty) {
    prop.selected = !prop.selected;
  }

  onGroupByChange(option: GroupByOption) {
    this.groupByOptions.forEach(item => {
      item.checked = item === option;
    });
  }

  onOrderByChange(selected: OrderByOption) {
    this.orderByOptions.forEach(option => {
      option.checked = option === selected;
    });
  }
}
