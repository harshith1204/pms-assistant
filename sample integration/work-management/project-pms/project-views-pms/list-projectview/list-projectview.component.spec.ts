import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ListProjectviewComponent } from './list-projectview.component';

describe('ListProjectviewComponent', () => {
  let component: ListProjectviewComponent;
  let fixture: ComponentFixture<ListProjectviewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ListProjectviewComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ListProjectviewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
