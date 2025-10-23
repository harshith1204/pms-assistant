import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AddEstimationComponent } from './add-estimation.component';

describe('AddEstimationComponent', () => {
  let component: AddEstimationComponent;
  let fixture: ComponentFixture<AddEstimationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ AddEstimationComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AddEstimationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
