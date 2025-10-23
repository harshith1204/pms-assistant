import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ListWorkitemComponent } from './list-workitem.component';

describe('ListWorkitemComponent', () => {
  let component: ListWorkitemComponent;
  let fixture: ComponentFixture<ListWorkitemComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ListWorkitemComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ListWorkitemComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
