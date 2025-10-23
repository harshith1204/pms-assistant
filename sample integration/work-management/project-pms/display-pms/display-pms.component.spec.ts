import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DisplayPmsComponent } from './display-pms.component';

describe('DisplayPmsComponent', () => {
  let component: DisplayPmsComponent;
  let fixture: ComponentFixture<DisplayPmsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DisplayPmsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DisplayPmsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
