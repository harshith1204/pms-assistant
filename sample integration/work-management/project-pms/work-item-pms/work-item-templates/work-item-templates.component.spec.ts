import { ComponentFixture, TestBed } from '@angular/core/testing';

import { WorkItemTemplatesComponent } from './work-item-templates.component';

describe('WorkItemTemplatesComponent', () => {
  let component: WorkItemTemplatesComponent;
  let fixture: ComponentFixture<WorkItemTemplatesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ WorkItemTemplatesComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(WorkItemTemplatesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
